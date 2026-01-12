"""
Gemini Policy Extractor Service
Uses Gemini 2.5 Flash to extract policy information from uploaded PDF documents
and provides tools for client database lookup with fuzzy matching.
"""

import os
import json
import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from google import genai
from google.genai import types
from supabase import create_client
from dynamic_config import Config

logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Product types available in the system
PRODUCT_TYPES = [
    "HEALTH INSURANCE",
    "MOTOR INSURANCE",
    "FACTORY INSURANCE",
    "LIFE INSURANCE",
    "TRAVEL INSURANCE",
    "BHARAT GRIHA RAKSHA",
    "BHARAT SOOKSHMA UDYAM SURAKSHA",
    "BHARAT LAGHU UDYAM SURAKSHA",
    "BHARAT GRIHA RAKSHA POLICY - LTD",
]


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class ClientInfo:
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    existing_client_id: Optional[str] = None
    existing_member_id: Optional[int] = None
    existing_member_name: Optional[str] = None
    confidence: str = ConfidenceLevel.NOT_FOUND


@dataclass
class PolicyDetails:
    insurance_company: Optional[str] = None
    product_name: Optional[str] = None
    policy_number: Optional[str] = None
    policy_from: Optional[str] = None  # DD/MM/YYYY
    policy_to: Optional[str] = None    # DD/MM/YYYY
    payment_date: Optional[str] = None
    payment_details: Optional[str] = None  # UPI/RTGS ref, cheque number, etc.
    net_premium: Optional[float] = None
    addon_premium: Optional[float] = None
    tp_tr_premium: Optional[float] = None
    gross_premium: Optional[float] = None
    sum_insured: Optional[float] = None
    agent_name: Optional[str] = None
    business_type: Optional[str] = None  # NEW, RENEWAL, ROLL OVER
    remarks: Optional[str] = None


@dataclass
class HealthMember:
    name: str
    sum_insured: Optional[float] = None
    bonus: Optional[float] = None
    deductible: Optional[float] = None


@dataclass
class HealthDetails:
    plan_type: Optional[str] = None  # FLOATER, INDIVIDUAL, TOPUP_FLOATER, TOPUP_INDIVIDUAL
    floater_sum_insured: Optional[float] = None
    floater_bonus: Optional[float] = None
    floater_deductible: Optional[float] = None
    members: List[HealthMember] = field(default_factory=list)


@dataclass
class FactoryDetails:
    building: Optional[float] = None
    plant_machinery: Optional[float] = None
    furniture_fittings: Optional[float] = None
    stocks: Optional[float] = None
    electrical_installations: Optional[float] = None


@dataclass
class PolicyExtractionResult:
    success: bool
    client_info: ClientInfo = field(default_factory=ClientInfo)
    policy_details: PolicyDetails = field(default_factory=PolicyDetails)
    health_details: Optional[HealthDetails] = None
    factory_details: Optional[FactoryDetails] = None
    fields_needing_review: List[str] = field(default_factory=list)
    extraction_notes: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization"""
        result = {
            "success": self.success,
            "client_info": asdict(self.client_info),
            "policy_details": asdict(self.policy_details),
            "fields_needing_review": self.fields_needing_review,
            "extraction_notes": self.extraction_notes,
        }
        if self.health_details:
            result["health_details"] = asdict(self.health_details)
        if self.factory_details:
            result["factory_details"] = asdict(self.factory_details)
        if self.error:
            result["error"] = self.error
        return result


def normalize_name(name: str) -> str:
    """Normalize a name for comparison - handles Dr., Mr., Mrs., etc."""
    if not name:
        return ""
    
    # Convert to lowercase
    name = name.lower().strip()
    
    # Remove common prefixes
    prefixes = ['dr.', 'dr', 'mr.', 'mr', 'mrs.', 'mrs', 'ms.', 'ms', 'shri', 'smt.', 'smt', 'prof.', 'prof']
    for prefix in prefixes:
        if name.startswith(prefix + ' '):
            name = name[len(prefix):].strip()
        elif name.startswith(prefix):
            name = name[len(prefix):].strip()
    
    # Remove extra spaces
    name = ' '.join(name.split())
    
    return name


def get_name_parts(name: str) -> List[str]:
    """Get individual parts of a name"""
    normalized = normalize_name(name)
    return [p for p in normalized.split() if len(p) > 1]  # Ignore single letters like initials


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names.
    Handles cases like:
    - "Dr Dhruv Shah" vs "Dr D. Shah"
    - "SAMEER NIRANJAN SHAH" vs "Sameer Shah"
    - Full name vs partial name
    """
    if not name1 or not name2:
        return 0.0
    
    parts1 = get_name_parts(name1)
    parts2 = get_name_parts(name2)
    
    if not parts1 or not parts2:
        return 0.0
    
    # Check for exact match after normalization
    if normalize_name(name1) == normalize_name(name2):
        return 1.0
    
    # Count matching parts
    matches = 0
    for p1 in parts1:
        for p2 in parts2:
            # Exact match
            if p1 == p2:
                matches += 1
                break
            # One is initial of another (e.g., "d" matches "dhruv")
            elif len(p1) == 1 and p2.startswith(p1):
                matches += 0.5
                break
            elif len(p2) == 1 and p1.startswith(p2):
                matches += 0.5
                break
            # Substring match for longer names
            elif len(p1) > 3 and len(p2) > 3 and (p1 in p2 or p2 in p1):
                matches += 0.7
                break
    
    # Calculate similarity as ratio of matches to total parts
    max_parts = max(len(parts1), len(parts2))
    return matches / max_parts if max_parts > 0 else 0.0


class GeminiPolicyExtractor:
    """Service for extracting policy data from documents using Gemini"""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set - policy extraction will not work")
        self.model = "gemini-2.5-flash"
        self.client = None
        
    def _get_client(self):
        """Lazy initialize Gemini client"""
        if self.client is None and self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        return self.client
    
    def lookup_client_and_member(self, name: str, phone: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Look up existing client AND member in database with fuzzy matching.
        Handles variations like "Dr Dhruv Shah" vs "Dr D. Shah".
        Also searches member names within clients.
        """
        try:
            # Get all clients for fuzzy matching
            clients_result = supabase.table("clients").select("client_id, name, phone, email").execute()
            
            if not clients_result.data:
                return {"found": False, "message": "No clients in database"}
            
            best_match = None
            best_score = 0.0
            match_type = None
            matched_member = None
            
            # Search through all clients
            for client in clients_result.data:
                client_name = client.get("name", "")
                
                # Calculate similarity with client name
                score = calculate_name_similarity(name, client_name)
                
                if score > best_score and score >= 0.5:  # Minimum 50% match threshold
                    best_score = score
                    best_match = client
                    match_type = "client_name"
                    matched_member = None
                
                # Also search in members for this client
                members_result = supabase.table("members").select("member_id, member_name").eq("client_id", client["client_id"]).execute()
                
                if members_result.data:
                    for member in members_result.data:
                        member_name = member.get("member_name", "")
                        member_score = calculate_name_similarity(name, member_name)
                        
                        if member_score > best_score and member_score >= 0.5:
                            best_score = member_score
                            best_match = client
                            match_type = "member_name"
                            matched_member = member
            
            # Also try phone lookup if provided
            if phone and best_score < 0.8:
                phone_normalized = re.sub(r'[^\d]', '', phone)[-10:]  # Last 10 digits
                
                for client in clients_result.data:
                    if client.get("phone"):
                        client_phone_normalized = re.sub(r'[^\d]', '', client["phone"])[-10:]
                        if phone_normalized == client_phone_normalized:
                            # Phone match is very reliable
                            best_match = client
                            best_score = 0.95
                            match_type = "phone"
                            # Get members for this client
                            members_result = supabase.table("members").select("member_id, member_name").eq("client_id", client["client_id"]).execute()
                            # Try to find member with similar name
                            if members_result.data:
                                for member in members_result.data:
                                    if calculate_name_similarity(name, member.get("member_name", "")) >= 0.5:
                                        matched_member = member
                                        break
                            break
            
            if best_match and best_score >= 0.5:
                # Get all members for the matched client
                all_members = supabase.table("members").select("member_id, member_name").eq("client_id", best_match["client_id"]).execute()
                
                result = {
                    "found": True,
                    "client_id": best_match["client_id"],
                    "client_name": best_match["name"],
                    "phone": best_match.get("phone"),
                    "email": best_match.get("email"),
                    "match_score": round(best_score, 2),
                    "match_type": match_type,
                    "members": all_members.data if all_members.data else []
                }
                
                if matched_member:
                    result["matched_member_id"] = matched_member["member_id"]
                    result["matched_member_name"] = matched_member["member_name"]
                
                return result
            
            return {"found": False, "message": f"No client found matching '{name}' (best score: {round(best_score, 2)})"}
            
        except Exception as e:
            logger.error(f"Error looking up client: {e}")
            import traceback
            traceback.print_exc()
            return {"found": False, "error": str(e)}
    
    def lookup_client(self, name: str, phone: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        """Alias for lookup_client_and_member for backward compatibility"""
        return self.lookup_client_and_member(name, phone, email)
    
    def extract_from_pdf(self, pdf_bytes: bytes, filename: str = "document.pdf") -> PolicyExtractionResult:
        """
        Extract policy information from a PDF document using OCR/vision.
        
        Args:
            pdf_bytes: Raw bytes of the PDF file
            filename: Original filename for context
            
        Returns:
            PolicyExtractionResult with extracted data
        """
        client = self._get_client()
        if not client:
            return PolicyExtractionResult(
                success=False,
                error="Gemini API key not configured"
            )
        
        try:
            # Build the extraction prompt with product list
            product_list = "\n".join([f"- {p}" for p in PRODUCT_TYPES])
            
            extraction_prompt = f"""You are an insurance document OCR and data extraction AI. 
IMPORTANT: Use your VISION capabilities to read ALL text from this PDF document image. Do not skip any pages.

Extract policy information and return as JSON. Here are the VALID PRODUCT TYPES in our system:
{product_list}

You MUST match the product to one of these exact values, or use the closest match.

EXTRACTION RULES:
1. **Agent Name**: Look for "Agent", "Advisor", "Producer", "Intermediary", "POSP", "Broker" fields. This is the sales person's name, not the customer.
2. **Payment Details**: Look for transaction ID, UTR, RTGS number, cheque number, UPI reference, payment reference.
3. **Remarks**: Only include USER notes or special instructions. Do NOT include standard policy terms, disclaimers, or legal text like "Policy void if cheque dishonoured".
4. **Dates**: Convert ALL dates to DD/MM/YYYY format.
5. **Policyholder Name**: This is the customer/insured person, NOT the agent or company.
6. **Phone/Email**: Extract the customer's contact details if visible.

Return this exact JSON structure:
{{
    "client_info": {{
        "name": "policyholder/insured full name",
        "phone": "phone number with country code or null",
        "email": "email address or null",
        "confidence": "HIGH/MEDIUM/LOW"
    }},
    "policy_details": {{
        "insurance_company": "full company name like 'ICICI Lombard General Insurance', 'HDFC ERGO', etc.",
        "product_name": "MUST be one of the valid product types listed above",
        "policy_number": "the policy/certificate number",
        "policy_from": "start date in DD/MM/YYYY",
        "policy_to": "end date in DD/MM/YYYY", 
        "payment_date": "payment/premium received date in DD/MM/YYYY or null",
        "payment_details": "transaction/UTR/cheque reference or null",
        "net_premium": "net/base premium amount as number",
        "addon_premium": "addon premium amount or null",
        "tp_tr_premium": "third party/terrorism premium or null",
        "gross_premium": "total/gross premium as number",
        "sum_insured": "total sum insured amount",
        "agent_name": "agent/advisor/broker name if mentioned, NOT the customer name",
        "business_type": "NEW or RENEWAL based on document",
        "remarks": "only actual user notes, NOT policy disclaimers or legal text"
    }},
    "health_details": {{
        "plan_type": "FLOATER/INDIVIDUAL/TOPUP_FLOATER/TOPUP_INDIVIDUAL or null",
        "floater_sum_insured": "shared sum insured for floater plans",
        "floater_bonus": "no claim bonus amount or null",
        "floater_deductible": "deductible amount or null",
        "members": [{{"name": "member name", "sum_insured": "individual SI or null"}}]
    }},
    "factory_details": {{
        "building": "building coverage amount or null",
        "plant_machinery": "plant & machinery coverage or null",
        "furniture_fittings": "furniture coverage or null",
        "stocks": "stock coverage or null",
        "electrical_installations": "electrical coverage or null"
    }},
    "fields_needing_review": ["list field names you couldn't find or are uncertain about"],
    "extraction_notes": "brief notes about the extraction"
}}

IMPORTANT:
- health_details: Only include if this is HEALTH INSURANCE or MEDICLAIM
- factory_details: Only include if this is FACTORY INSURANCE, FIRE, SFSP, or BHARAT UDYAM policies
- Use null for any field you cannot find
- Do NOT make up data - use null if not visible in document"""

            # Configuration for JSON response with vision
            generate_config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            
            # Generate content with PDF - using vision/OCR
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    extraction_prompt
                ],
                config=generate_config,
            )
            
            # Parse the JSON response
            response_text = response.text
            logger.info(f"Gemini extraction response length: {len(response_text)} chars")
            
            extracted_data = json.loads(response_text)
            
            # Build the result object
            result = PolicyExtractionResult(success=True)
            
            # Parse client info
            if "client_info" in extracted_data:
                ci = extracted_data["client_info"]
                result.client_info = ClientInfo(
                    name=ci.get("name"),
                    phone=ci.get("phone"),
                    email=ci.get("email"),
                    confidence=ci.get("confidence", ConfidenceLevel.NOT_FOUND)
                )
                
                # Try to look up client in database with fuzzy matching
                if result.client_info.name:
                    lookup_result = self.lookup_client_and_member(
                        result.client_info.name,
                        result.client_info.phone,
                        result.client_info.email
                    )
                    logger.info(f"Client lookup result: {lookup_result}")
                    
                    if lookup_result.get("found"):
                        result.client_info.existing_client_id = lookup_result["client_id"]
                        result.client_info.confidence = ConfidenceLevel.HIGH if lookup_result.get("match_score", 0) >= 0.8 else ConfidenceLevel.MEDIUM
                        
                        # Set matched member if found
                        if lookup_result.get("matched_member_id"):
                            result.client_info.existing_member_id = lookup_result["matched_member_id"]
                            result.client_info.existing_member_name = lookup_result.get("matched_member_name")
                        elif lookup_result.get("members"):
                            # Use first member if no specific match
                            result.client_info.existing_member_id = lookup_result["members"][0].get("member_id")
                            result.client_info.existing_member_name = lookup_result["members"][0].get("member_name")
            
            # Parse policy details
            if "policy_details" in extracted_data:
                pd = extracted_data["policy_details"]
                result.policy_details = PolicyDetails(
                    insurance_company=pd.get("insurance_company"),
                    product_name=pd.get("product_name"),
                    policy_number=pd.get("policy_number"),
                    policy_from=pd.get("policy_from"),
                    policy_to=pd.get("policy_to"),
                    payment_date=pd.get("payment_date"),
                    payment_details=pd.get("payment_details"),
                    net_premium=pd.get("net_premium"),
                    addon_premium=pd.get("addon_premium"),
                    tp_tr_premium=pd.get("tp_tr_premium"),
                    gross_premium=pd.get("gross_premium"),
                    sum_insured=pd.get("sum_insured"),
                    agent_name=pd.get("agent_name"),
                    business_type=pd.get("business_type"),
                    remarks=pd.get("remarks")
                )
                
                # Clean up remarks - remove common disclaimer text
                if result.policy_details.remarks:
                    disclaimer_patterns = [
                        r'policy.*void.*cheque',
                        r'ab.?initio',
                        r'dishonour',
                        r'terms.*conditions.*apply',
                        r'subject.*verification',
                    ]
                    remarks_lower = result.policy_details.remarks.lower()
                    for pattern in disclaimer_patterns:
                        if re.search(pattern, remarks_lower, re.IGNORECASE):
                            result.policy_details.remarks = None
                            break
            
            # Parse health details if present
            if "health_details" in extracted_data and extracted_data["health_details"]:
                hd = extracted_data["health_details"]
                if hd.get("plan_type"):  # Only include if there's actual data
                    members = []
                    if hd.get("members"):
                        for m in hd["members"]:
                            if m.get("name"):  # Only add if member has a name
                                members.append(HealthMember(
                                    name=m.get("name", ""),
                                    sum_insured=m.get("sum_insured"),
                                    bonus=m.get("bonus"),
                                    deductible=m.get("deductible")
                                ))
                    result.health_details = HealthDetails(
                        plan_type=hd.get("plan_type"),
                        floater_sum_insured=hd.get("floater_sum_insured"),
                        floater_bonus=hd.get("floater_bonus"),
                        floater_deductible=hd.get("floater_deductible"),
                        members=members
                    )
            
            # Parse factory details if present
            if "factory_details" in extracted_data and extracted_data["factory_details"]:
                fd = extracted_data["factory_details"]
                # Only include if there's actual data
                if any(fd.get(k) for k in ["building", "plant_machinery", "furniture_fittings", "stocks", "electrical_installations"]):
                    result.factory_details = FactoryDetails(
                        building=fd.get("building"),
                        plant_machinery=fd.get("plant_machinery"),
                        furniture_fittings=fd.get("furniture_fittings"),
                        stocks=fd.get("stocks"),
                        electrical_installations=fd.get("electrical_installations")
                    )
            
            # Add fields needing review and notes
            result.fields_needing_review = extracted_data.get("fields_needing_review", [])
            result.extraction_notes = extracted_data.get("extraction_notes", "")
            
            logger.info(f"Successfully extracted policy data from {filename}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            return PolicyExtractionResult(
                success=False,
                error=f"Failed to parse extraction response: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error extracting policy data: {e}")
            import traceback
            traceback.print_exc()
            return PolicyExtractionResult(
                success=False,
                error=f"Extraction failed: {str(e)}"
            )


# Singleton instance
policy_extractor = GeminiPolicyExtractor()
