"""
Settings Service - Manages application settings stored in database
Replaces hardcoded configuration values with database-driven settings
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from supabase import create_client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class SettingsService:
    """Service for managing application settings"""
    
    def __init__(self):
        # Initialize with environment variables for database connection
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
            
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        self._cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes cache TTL
    
    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed"""
        if not self._cache_timestamp:
            return True
        return (datetime.now() - self._cache_timestamp).seconds > self._cache_ttl
    
    def _refresh_cache(self):
        """Refresh settings cache from database"""
        try:
            result = self.supabase.table('settings').select('*').execute()
            
            self._cache = {}
            for setting in result.data:
                category = setting['category']
                key = setting['key']
                
                if category not in self._cache:
                    self._cache[category] = {}
                
                # Convert value based on data type
                value = self._convert_value(setting['value'], setting['data_type'])
                self._cache[category][key] = {
                    'value': value,
                    'data_type': setting['data_type'],
                    'description': setting['description'],
                    'is_sensitive': setting['is_sensitive']
                }
            
            self._cache_timestamp = datetime.now()
            logger.info("Settings cache refreshed successfully")
            
        except Exception as e:
            logger.error(f"Error refreshing settings cache: {e}")
            # Keep existing cache if refresh fails
    
    def _convert_value(self, value: str, data_type: str) -> Any:
        """Convert string value to appropriate type"""
        if value is None:
            return None
            
        try:
            if data_type == 'boolean':
                return value.lower() in ('true', '1', 'yes', 'on')
            elif data_type == 'number':
                if '.' in value:
                    return float(value)
                return int(value)
            elif data_type == 'json':
                return json.loads(value)
            else:  # string
                return value
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error converting value '{value}' to {data_type}: {e}")
            return value  # Return as string if conversion fails
    
    def get(self, category: str, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        if self._should_refresh_cache():
            self._refresh_cache()
        
        try:
            return self._cache.get(category, {}).get(key, {}).get('value', default)
        except Exception as e:
            logger.error(f"Error getting setting {category}.{key}: {e}")
            return default
    
    def get_category(self, category: str) -> Dict[str, Any]:
        """Get all settings in a category"""
        if self._should_refresh_cache():
            self._refresh_cache()
        
        category_settings = self._cache.get(category, {})
        return {key: data['value'] for key, data in category_settings.items()}
    
    def get_all_categories(self) -> List[str]:
        """Get list of all setting categories"""
        if self._should_refresh_cache():
            self._refresh_cache()
        
        return list(self._cache.keys())
    
    def get_category_with_metadata(self, category: str) -> Dict[str, Dict]:
        """Get all settings in a category with metadata"""
        if self._should_refresh_cache():
            self._refresh_cache()
        
        return self._cache.get(category, {})
    
    def set(self, category: str, key: str, value: Any, updated_by: str = None) -> bool:
        """Set a setting value"""
        try:
            # Convert value to string for storage
            if isinstance(value, (dict, list)):
                str_value = json.dumps(value)
                data_type = 'json'
            elif isinstance(value, bool):
                str_value = str(value).lower()
                data_type = 'boolean'
            elif isinstance(value, (int, float)):
                str_value = str(value)
                data_type = 'number'
            else:
                str_value = str(value)
                data_type = 'string'
            
            # Update in database
            update_data = {
                'value': str_value,
                'data_type': data_type,
                'updated_at': datetime.now().isoformat()
            }
            
            if updated_by:
                update_data['updated_by'] = updated_by
            
            result = self.supabase.table('settings').update(update_data).eq('category', category).eq('key', key).execute()
            
            if result.data:
                # Update cache
                if category not in self._cache:
                    self._cache[category] = {}
                
                if key in self._cache[category]:
                    self._cache[category][key]['value'] = self._convert_value(str_value, data_type)
                    self._cache[category][key]['data_type'] = data_type
                
                logger.info(f"Setting {category}.{key} updated successfully")
                return True
            else:
                logger.error(f"Failed to update setting {category}.{key}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting {category}.{key}: {e}")
            return False
    
    def create(self, category: str, key: str, value: Any, description: str = "", 
               is_sensitive: bool = False, updated_by: str = None) -> bool:
        """Create a new setting"""
        try:
            # Convert value to string for storage
            if isinstance(value, (dict, list)):
                str_value = json.dumps(value)
                data_type = 'json'
            elif isinstance(value, bool):
                str_value = str(value).lower()
                data_type = 'boolean'
            elif isinstance(value, (int, float)):
                str_value = str(value)
                data_type = 'number'
            else:
                str_value = str(value)
                data_type = 'string'
            
            insert_data = {
                'category': category,
                'key': key,
                'value': str_value,
                'data_type': data_type,
                'description': description,
                'is_sensitive': is_sensitive
            }
            
            if updated_by:
                insert_data['updated_by'] = updated_by
            
            result = self.supabase.table('settings').insert(insert_data).execute()
            
            if result.data:
                # Refresh cache to include new setting
                self._refresh_cache()
                logger.info(f"Setting {category}.{key} created successfully")
                return True
            else:
                logger.error(f"Failed to create setting {category}.{key}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating setting {category}.{key}: {e}")
            return False
    
    def delete(self, category: str, key: str) -> bool:
        """Delete a setting"""
        try:
            result = self.supabase.table('settings').delete().eq('category', category).eq('key', key).execute()
            
            if result.data:
                # Remove from cache
                if category in self._cache and key in self._cache[category]:
                    del self._cache[category][key]
                    if not self._cache[category]:  # Remove empty category
                        del self._cache[category]
                
                logger.info(f"Setting {category}.{key} deleted successfully")
                return True
            else:
                logger.error(f"Failed to delete setting {category}.{key}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting setting {category}.{key}: {e}")
            return False
    
    def get_all_settings(self) -> Dict[str, Dict[str, Dict]]:
        """Get all settings with metadata (for admin interface)"""
        if self._should_refresh_cache():
            self._refresh_cache()
        
        return self._cache.copy()
    
    def bulk_update(self, settings: Dict[str, Dict[str, Any]], updated_by: str = None) -> bool:
        """Bulk update multiple settings"""
        success_count = 0
        total_count = 0
        
        for category, category_settings in settings.items():
            for key, value in category_settings.items():
                total_count += 1
                if self.set(category, key, value, updated_by):
                    success_count += 1
        
        logger.info(f"Bulk update completed: {success_count}/{total_count} settings updated")
        return success_count == total_count
    
    def export_settings(self, include_sensitive: bool = False) -> Dict:
        """Export settings for backup/migration"""
        if self._should_refresh_cache():
            self._refresh_cache()
        
        export_data = {}
        for category, category_settings in self._cache.items():
            export_data[category] = {}
            for key, data in category_settings.items():
                if not include_sensitive and data.get('is_sensitive', False):
                    continue
                export_data[category][key] = {
                    'value': data['value'],
                    'data_type': data['data_type'],
                    'description': data['description'],
                    'is_sensitive': data['is_sensitive']
                }
        
        return export_data
    
    def clear_cache(self):
        """Clear the settings cache"""
        self._cache = {}
        self._cache_timestamp = None
        logger.info("Settings cache cleared")


# Global settings instance
settings = SettingsService()

# Convenience functions for common operations
def get_setting(category: str, key: str, default: Any = None) -> Any:
    """Get a setting value - convenience function"""
    return settings.get(category, key, default)

def set_setting(category: str, key: str, value: Any, updated_by: str = None) -> bool:
    """Set a setting value - convenience function"""
    return settings.set(category, key, value, updated_by)

def get_company_settings() -> Dict[str, Any]:
    """Get all company settings"""
    return settings.get_category('company')

def get_email_settings() -> Dict[str, Any]:
    """Get all email settings"""
    return settings.get_category('email')

def get_whatsapp_settings() -> Dict[str, Any]:
    """Get all WhatsApp settings"""
    return settings.get_category('whatsapp')

def get_twilio_settings() -> Dict[str, Any]:
    """Get all Twilio settings"""
    return settings.get_category('twilio')

def get_google_drive_settings() -> Dict[str, Any]:
    """Get all Google Drive settings"""
    return settings.get_category('google_drive')

def get_app_settings() -> Dict[str, Any]:
    """Get all application settings"""
    return settings.get_category('app')
