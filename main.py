import os
import time
import secure
import uuid

from config import settings
from dependencies import validate_token

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, AnyHttpUrl
from typing import Optional
import libsql_client
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(openapi_url=None)

csp = secure.ContentSecurityPolicy().default_src("'self'").frame_ancestors("'none'")
hsts = secure.StrictTransportSecurity().max_age(31536000).include_subdomains()
referrer = secure.ReferrerPolicy().no_referrer()
cache_value = secure.CacheControl().no_cache().no_store().max_age(0).must_revalidate()
x_frame_options = secure.XFrameOptions().deny()

secure_headers = secure.Secure(
    csp=csp,
    hsts=hsts,
    referrer=referrer,
    cache=cache_value,
    xfo=x_frame_options,
)

# this is necessary to close the client
# at the end of the session
async def get_client():
   # connect to turso db
  client = libsql_client.create_client(
      url=os.environ.get("turso_url_ams"),
      auth_token=os.environ.get("turso_auth_token")
  )
  try:
     yield client
  finally:
     await client.close()

class CreateLinkComment(BaseModel):
    url: AnyHttpUrl
    comment: str

class CreationResponse(BaseModel):
    id: str

class ReturnLinkComment(BaseModel):
   id: str
   link: str
   comment: str
   created_at: float
   updated_at: Optional[float]
  
@app.middleware("http")
async def set_secure_headers(request, call_next):
    response = await call_next(request)
    secure_headers.framework.fastapi(response)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_origins=[settings.client_origin_url],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    # allow_headers=["Authorization", "Content-Type"],
    max_age=86400,
)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    message = str(exc.detail)

    return JSONResponse({"message": message}, status_code=exc.status_code)


@app.get("/healthcheck")
async def read_root():
     return {"status": "ok"}

# create a link comment
@app.post("/linkcomment")
async def create_link_comment(link_comment: CreateLinkComment, dependencies=[Depends(validate_token)], client = Depends(get_client)) -> CreationResponse:

    linkcomment_id = str(uuid.uuid4())
    user_id = dependencies.get("sub")
    
    try:
      result_set = await client.execute(
          "insert into linkcomment values (:id, :link, :comment, :username, :created_at, :updated_at)", 
          {"id": linkcomment_id, "link": link_comment.url, "comment": link_comment.comment, "username": user_id, "created_at": time.time(), "updated_at": None}
        )
      return {"id": linkcomment_id}
    except:
        raise HTTPException(500, "error creating link-comment")

# get links and comments per user 
structure = ["id", "link", "comment", "created_at", "updated_at"]

@app.get("/linkcomment")
async def get_link_comments(dependencies=[Depends(validate_token)], client = Depends(get_client)) -> list[ReturnLinkComment]:
  user_id = "aZIDN7hez7tu6lK1iljym68C6GBnZR6O@clients"
  try:
     result_set = await client.execute("select id, link, comment, created_at, updated_at from linkcomment where username=:user_id", {"user_id": user_id})
     
     # transfor list of tuples in to list of objects
     return_value = []
     for row in result_set.rows:
        return_dict = {}
        for i in range(0, len(row)):
           return_dict[structure[i]] = row[i]
        return_value.append(return_dict)
      
     return return_value
  except:
    raise HTTPException(500, "error reading links and comments")

@app.delete("/linkcomment/{lc_id}")
async def delete_link_comment(lc_id: str, dependencies=[Depends(validate_token)], client = Depends(get_client)):
   user_id = dependencies.get("sub")
   
   try:
      result_set = await client.execute("delete from linkcomment where username=:user_id and id=:lc_id", {"user_id": user_id, "lc_id": lc_id})
      return {"id": lc_id}
   except:
      raise HTTPException(500, "error deleting link comment")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.reload,
        server_header=False,
    )