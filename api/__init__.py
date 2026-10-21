"""API HTTP del asistente (fase 0 del plan de interfaz propia, 21/10/2026).

Corre al lado de la app de Streamlit, sobre los mismos módulos (nucleo, db). Este paquete solo agrega
la raíz del repo al sys.path para que `import nucleo` funcione se corra desde donde se corra.
"""
import os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
