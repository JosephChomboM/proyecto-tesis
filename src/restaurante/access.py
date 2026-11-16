"""Small shared-access gate for the single-administrator research deployment."""

import hashlib
import hmac
import os
import time

import streamlit as st

from .presentation import brand, page_header


def is_public_demo():
    return os.environ.get("RESTAURANTE_PUBLIC_DEMO", "").lower() == "true"


def require_access():
    # This flag only exposes the isolated synthetic sandbox, never the own-restaurant files.
    if is_public_demo():
        return True
    expected = os.environ.get("RESTAURANTE_ACCESS_PASSWORD", "")
    hosted = os.environ.get("RENDER", "").lower() == "true"
    if not expected and not hosted:
        return True
    if len(expected) < 16:
        page_header("CONFIGURACIÓN PENDIENTE", "El acceso todavía no está habilitado",
                    "Configura la clave de acceso en el entorno del servidor para continuar.")
        return False
    fingerprint = hashlib.sha256(expected.encode()).hexdigest()
    if hmac.compare_digest(st.session_state.get("access_grant", ""), fingerprint):
        with st.sidebar:
            if st.button("Cerrar sesión", icon=":material/logout:"):
                st.session_state.clear()
                st.rerun()
        return True
    brand()
    page_header("ACCESO AL RESTAURANTE", "Bienvenido a tu cocina",
                "Ingresa la clave compartida por el administrador para abrir este espacio.")
    blocked_until = st.session_state.get("access_blocked_until", 0)
    if blocked_until > time.monotonic():
        st.warning("Espera un minuto antes de intentar de nuevo.")
        return False
    with st.form("access_form", clear_on_submit=True):
        password = st.text_input("Clave de acceso", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted:
        if hmac.compare_digest(password.encode(), expected.encode()):
            st.session_state["access_grant"] = fingerprint
            st.session_state.pop("access_attempts", None)
            st.session_state.pop("access_blocked_until", None)
            st.rerun()
        else:
            attempts = st.session_state.get("access_attempts", 0) + 1
            st.session_state["access_attempts"] = attempts
            if attempts >= 5:
                st.session_state["access_blocked_until"] = time.monotonic() + 60
                st.session_state["access_attempts"] = 0
            st.error("La clave no es correcta.")
    st.caption("Acceso compartido para evaluación. Todos los participantes autorizados usan el mismo inventario.")
    return False
