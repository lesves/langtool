from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model, get_backends, authenticate
from django.conf import settings

import jwt
import time


class TokenBackend(ModelBackend):
    """
    Use a JWT token to authenticate.
    """

    @staticmethod
    def get_token_from_headers(request, prefix="Bearer "):
        token = request.headers.get("Authorization")
        if token is None or not token.startswith(prefix):
            return None
        return token[len(prefix):]

    def authenticate(self, request, token=None):
        token = token or self.get_token_from_headers(request)

        if token is None:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], require=["exp"])
        except jwt.PyJWTError:
            return None

        if payload.get("exp") is None or payload.get("username") is None:
            # Only take tokens with an expiration and the authenticating user set
            return None

        if payload["exp"] <= int(time.time()):
            # Expired
            return None

        try:
            User = get_user_model()
            return User.objects.get(username=payload["username"])
        except User.DoesNotExist:
            return None


class JWTAuthenticationMiddleware:
    def __init__(self, get_response):
        self.backends = get_backends()
        self.get_response = get_response

    def __call__(self, request):
        for backend in self.backends:
            if isinstance(backend, TokenBackend):
                if not request.user.is_authenticated:
                    user = backend.authenticate(request)
                    if user is not None:
                        request.user = user
                break

        return self.get_response(request)


def create_jwt_token(user, validity=2592000, exp=None):
    """
    Create a JWT token that can be used to authenticate a given user.
    If exp is supplied, the token expires at time exp (in seconds since epoch).
    If exp is not supplied, the token expires at current time plus validity 
    (validity defaults to one month).
    """
    if exp is None:
        exp = int(time.time())+validity

    payload = {
        "username": user.username, 
        "exp": exp
    }
    return jwt.encode(payload, key=settings.SECRET_KEY, algorithm="HS256")


def issue_jwt_token(username, password, validity=2592000, exp=None):
    """
    Same as create_jwt_token but first finds and authenticates
    the user using a username and a password.
    """
    user = authenticate(username=username, password=password)

    if user is not None:
        return create_jwt_token(user, validity=validity, exp=exp)

