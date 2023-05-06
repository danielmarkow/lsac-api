import jwt
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, AnyHttpUrl
import libsql_client
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
token_auth_scheme = HTTPBearer()

# this is necessary to close the client
# at the end of the session
async def get_client():
   # connect to turso db
  client = libsql_client.create_client(
      url=os.environ.get("turso_url"),
      auth_token=os.environ.get("turso_auth_token")
  )
  try:
     yield client
  finally:
     await client.close()

class LinkComment(BaseModel):
    url: AnyHttpUrl
    comment: str

class Response(BaseModel):
    id: str

def verify_token(token: str):
    # https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets
    jwks_url = f'https://{os.environ.get("DOMAIN")}/.well-known/jwks.json'
    jwks_client = jwt.PyJWKClient(jwks_url)

    try:
      signing_key = jwks_client.get_signing_key_from_jwt(token).key
    except jwt.exceptions.PyJWKClientError as error:
      return {"status": "error", "msg": error.__str__()}
    except jwt.exceptions.DecodeError as error:
      return {"status": "error", "msg": error.__str__()}

    try:
      payload = jwt.decode(
          token,
          signing_key,
          algorithms=os.environ.get("ALGORITHMS"),
          audience=os.environ.get("API_AUDIENCE"),
          issuer=os.environ.get("ISSUER"),
        )
    except Exception as e:
      return {"status": "error", "message": str(e)}

    return payload
    


@app.get("/")
async def root():
    return {"message" : "hello world"}

@app.post("/linkcomment")
async def create_link_comment(link_comment: LinkComment, token: str = Depends(token_auth_scheme), client = Depends(get_client)) -> Response:
    credentials = token.credentials
    verification_result = verify_token(credentials)

    if (verification_result.get("status")):
       raise HTTPException(400, "bad request")

    linkcomment_id = str(uuid.uuid4())
    user_id = verification_result.get("sub")
    
    try:
      result_set = await client.execute(
          "insert into linkcomment values (:id, :link, :comment, :username, :created_at, :updated_at)", 
          {"id": linkcomment_id, "link": link_comment.url, "comment": link_comment.comment, "username": user_id, "created_at": time.time(), "updated_at": None}
        )
      return {"id": linkcomment_id}
    except:
        raise HTTPException(500, "error creating link-comment")

# @app.get()


    