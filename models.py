from flask_login import UserMixin
from supabase import create_client
from config import Config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

class User(UserMixin):
    def __init__(self, email, name=None, picture=None, user_id=None):
        self.id = email  # Flask-Login needs this
        self.email = email
        self.name = name or email.split('@')[0]
        self.picture = picture
        self.user_id = user_id
        self.is_admin = email in Config.ADMIN_EMAILS
        self.last_login = datetime.now()

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
                    name=name or user_data.get('name'),
                    picture=picture or user_data.get('picture'),
                    user_id=user_data.get('id')
                )
            else:
                # Create new user
                new_user = {
                    'email': email,
                    'name': name or email.split('@')[0],
                    'picture': picture,
                    'is_admin': email in Config.ADMIN_EMAILS,
                    'created_at': datetime.now().isoformat(),
                    'last_login': datetime.now().isoformat()
                }
                
                result = supabase.table('users').insert(new_user).execute()
                user_data = result.data[0] if result.data else {}
                
                logger.info(f"Created new user: {email}")
                return User(
                    email=email,
                    name=name,
                    picture=picture,
                    user_id=user_data.get('id')
                )
                
        except Exception as e:
            logger.error(f"Error creating/getting user {email}: {e}")
            # Fallback to basic user object
            return User(email=email, name=name, picture=picture)

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
            'is_admin': self.is_admin,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create User object from dictionary (for cache retrieval)"""
        user = cls(
            email=data.get('email'),
            name=data.get('name'),
            picture=data.get('picture'),
            user_id=data.get('user_id')
        )
        user.is_admin = data.get('is_admin', False)
        if data.get('last_login'):
            try:
                user.last_login = datetime.fromisoformat(data['last_login'])
            except:
                user.last_login = datetime.now()
        return user
