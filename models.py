from flask_login import UserMixin
from supabase import create_client
from dynamic_config import Config
import logging
from datetime import datetime
import bcrypt

logger = logging.getLogger(__name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

class User(UserMixin):
    def __init__(self, email, name=None, picture=None, user_id=None, password_hash=None, role=None):
        self.id = email  # Flask-Login needs this
        self.email = email
        self.name = name or email.split('@')[0]
        self.picture = picture
        self.user_id = user_id
        self.password_hash = password_hash
        self.role = role or 'member'  # Default to member role
        self.is_admin = self.role == 'admin'
        self.last_login = datetime.now()

    def check_password(self, password):
        """Check if the provided password matches the stored hash"""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    @staticmethod
    def hash_password(password):
        """Hash a password for storing in the database"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def from_dict(data):
        """Create user object from dictionary (for caching)"""
        return User(
            email=data['email'],
            name=data['name'],
            picture=data.get('picture'),
            user_id=data.get('user_id'),
            password_hash=data.get('password_hash'),
            role=data.get('role', 'member')
        )

    @staticmethod
    def get_or_create(email, name=None, picture=None):
        """Create or update user in database and return User object"""
        try:
            # Check if user exists in database
            result = supabase.table('users').select('*').eq('email', email).execute()
            
            if result.data:
                # User exists, update last login
                user_data = result.data[0]
                supabase.table('users').update({
                    'last_login': datetime.now().isoformat(),
                    'name': name or user_data.get('name'),
                    'picture': picture or user_data.get('picture')
                }).eq('email', email).execute()
                
                return User(
                    email=email,
                    name=user_data.get('name'),
                    picture=user_data.get('picture'),
                    user_id=user_data.get('id'),
                    password_hash=user_data.get('password_hash'),
                    role=user_data.get('role', 'member')
                )
            else:
                # Create new user - first user becomes admin, others become members
                # Check if this is the first user
                user_count_result = supabase.table('users').select('id', count='exact').execute()
                is_first_user = user_count_result.count == 0
                
                new_user_data = {
                    'email': email,
                    'name': name or email.split('@')[0],
                    'picture': picture,
                    'role': 'admin' if is_first_user else 'member',
                    'is_admin': is_first_user,  # Keep for backward compatibility
                    'last_login': datetime.now().isoformat()
                }
                
                result = supabase.table('users').insert(new_user_data).execute()
                
                if result.data:
                    user_data = result.data[0]
                    return User(
                        email=email,
                        name=user_data.get('name'),
                        picture=user_data.get('picture'),
                        user_id=user_data.get('id'),
                        password_hash=user_data.get('password_hash'),
                        role=user_data.get('role', 'member')
                    )
                else:
                    logger.error(f"Failed to create user: {result}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error in get_or_create: {e}")
            return None

    @staticmethod
    def authenticate(email, password):
        """Authenticate user with email and password"""
        try:
            # Check if user exists and get password hash
            result = supabase.table('users').select('*').eq('email', email).execute()
            
            if not result.data:
                logger.warning(f"Authentication failed: User {email} not found")
                return None
                
            user_data = result.data[0]
            
            # Check if user is active
            if not user_data.get('is_active', True):
                logger.warning(f"Authentication failed: User {email} is not active")
                return None
            
            # Check password
            password_hash = user_data.get('password_hash')
            if not password_hash:
                logger.warning(f"Authentication failed: No password set for user {email}")
                return None
                
            if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                logger.warning(f"Authentication failed: Invalid password for user {email}")
                return None
            
            # Update last login
            supabase.table('users').update({
                'last_login': datetime.now().isoformat()
            }).eq('email', email).execute()
            
            logger.info(f"User {email} authenticated successfully")
            
            return User(
                email=email,
                name=user_data.get('name'),
                picture=user_data.get('picture'),
                user_id=user_data.get('id'),
                password_hash=password_hash,
                role=user_data.get('role', 'member')
            )
            
        except Exception as e:
            logger.error(f"Error in authenticate: {e}")
            return None

    def get_id(self):
        """Required by Flask-Login"""
        return self.email
    
    def is_authenticated(self):
        """Required by Flask-Login"""
        return True
    
    def is_active(self):
        """Required by Flask-Login"""
        return True
    
    def is_anonymous(self):
        """Required by Flask-Login"""
        return False
    
    def to_dict(self):
        """Convert User object to dictionary for caching"""
        return {
            'email': self.email,
            'name': self.name,
            'picture': self.picture,
            'user_id': self.user_id,
            'role': self.role,
            'is_admin': self.is_admin,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    @staticmethod
    def get_all_users():
        """Get all users for admin management"""
        try:
            result = supabase.table('users').select('*').order('created_at', desc=True).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    @staticmethod
    def update_user_role(email, new_role, updated_by=None):
        """Update user role (admin only)"""
        try:
            if new_role not in ['admin', 'member']:
                return False, "Invalid role. Must be 'admin' or 'member'"
            
            update_data = {
                'role': new_role,
                'is_admin': new_role == 'admin',
                'updated_at': datetime.now().isoformat()
            }
            
            result = supabase.table('users').update(update_data).eq('email', email).execute()
            
            if result.data:
                logger.info(f"User {email} role updated to {new_role} by {updated_by}")
                return True, "Role updated successfully"
            else:
                return False, "Failed to update user role"
                
        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return False, str(e)
    
    @staticmethod
    def create_user_with_password(email, name, password, role='member', created_by=None):
        """Create a new user with password (admin only)"""
        try:
            # Check if user already exists
            existing = supabase.table('users').select('email').eq('email', email).execute()
            if existing.data:
                return False, "User already exists"
            
            if role not in ['admin', 'member']:
                return False, "Invalid role. Must be 'admin' or 'member'"
            
            password_hash = User.hash_password(password)
            
            user_data = {
                'email': email,
                'name': name,
                'role': role,
                'is_admin': role == 'admin',
                'password_hash': password_hash,
                'created_at': datetime.now().isoformat(),
                'last_login': None
            }
            
            result = supabase.table('users').insert(user_data).execute()
            
            if result.data:
                logger.info(f"User {email} created with role {role} by {created_by}")
                return True, "User created successfully"
            else:
                return False, "Failed to create user"
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False, str(e)
    
    @staticmethod
    def delete_user(email, deleted_by=None):
        """Delete a user (admin only)"""
        try:
            result = supabase.table('users').delete().eq('email', email).execute()
            
            if result.data:
                logger.info(f"User {email} deleted by {deleted_by}")
                return True, "User deleted successfully"
            else:
                return False, "Failed to delete user"
                
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False, str(e)
    
    @staticmethod
    def reset_user_password(email, new_password, reset_by=None):
        """Reset user password (admin only)"""
        try:
            password_hash = User.hash_password(new_password)
            
            update_data = {
                'password_hash': password_hash
            }
            
            result = supabase.table('users').update(update_data).eq('email', email).execute()
            
            if result.data:
                logger.info(f"Password reset for user {email} by {reset_by}")
                return True, "Password reset successfully"
            else:
                return False, "Failed to reset password"
                
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return False, str(e)
