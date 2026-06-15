"""Reglas de negocio del catálogo de cartas.

La validación de imágenes está centralizada en
pokegrading.compartido.imagenes — importar desde ahí.
"""

from pokegrading.compartido.imagenes import validar_imagen

__all__ = ["validar_imagen"]
