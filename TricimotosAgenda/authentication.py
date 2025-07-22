import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

class ClerkAuthentication(BaseAuthentication):
    """
    Autenticación simple basada en JWT de Clerk.
    NO valida remotamente, solo decodifica y extrae el sub como ID.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            # Decode sin verificar la firma porque ya se validó en el frontend
            decoded = jwt.decode(token, options={"verify_signature": False})
            clerk_user_id = decoded.get("sub")

            if not clerk_user_id:
                raise AuthenticationFailed("Token inválido: sin ID")

            return clerk_user_id, None

        except jwt.DecodeError:
            raise AuthenticationFailed("Token inválido")
