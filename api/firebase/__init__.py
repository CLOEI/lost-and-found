from firebase_admin import auth, initialize_app, credentials
from os import getenv
import json


def cleanup_key(key):
  return key.replace('\\n', '\n') if key else ''

class Firebase:
  app = None
  def __init__(self):
    cred = credentials.Certificate(json.loads(getenv('FIREBASE_SERVICE_ACCOUNT')))
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