from firebase_admin import auth, initialize_app, credentials
from os import getenv


def cleanup_key(key):
  return key.replace('\\n', '\n') if key else ''

class Firebase:
  app = None
  def __init__(self):
    cred = credentials.Certificate({
      'type': getenv('type'),
      'project_id': getenv('project_id'),
      'private_key_id': getenv('private_key_id'),
      'private_key': cleanup_key(getenv('private_key')),
      'client_email': getenv('client_email'),
      'client_id': getenv('client_id'),
      'auth_uri': getenv('auth_uri'),
      'token_uri': getenv('token_uri'),
      'auth_provider_x509_cert_url': getenv('auth_provider_x509_cert_url'),
      'client_x509_cert_url': getenv('client_x509_cert_url'),
      'universe_domain': getenv('universe_domain')      
    })
    self.app = initialize_app(credential=cred)
  def register_user(self, email:str, display_name: str, password: str):
    user = auth.create_user(email=email, password=password, display_name=display_name, app=self.app)
    return auth.create_custom_token(user.uid, app=self.app)
  def token_is_valid(self, token: str):
    try:
      auth.verify_id_token(token, app=self.app)
      return True
    except:
      return False