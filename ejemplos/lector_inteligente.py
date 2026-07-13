"""
Lector inteligente de columnas para Excel/CSV.

Técnica: en vez de leer columnas por POSICIÓN fija (frágil: si mueven una columna,
todo se rompe), detecta cada campo por el NOMBRE de su encabezado, usando:

  1. Normalización  -> ignora mayúsculas, tildes y espacios ("Correo Electrónico"
                       == "correo_electronico").
  2. Diccionario de sinónimos por campo ("correo", "email", "e-mail"...).
  3. Coincidencia difusa (difflib) -> tolera errores de tipeo o encabezados
     mal codificados ("identificacin" ~ "identificación").

Así el archivo funciona aunque reordenen o renombren ligeramente las columnas.
Reimplementación genérica de una técnica que desarrollé en un proyecto real de RPA.

Ejecuta:  python lector_inteligente.py
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from difflib import SequenceMatcher

# Sinónimos aceptados por cada campo lógico (agrega los que necesites).
SINONIMOS = {
    "documento": ["documento", "cedula", "identificacion", "nit", "dni", "id"],
    "nombre":    ["nombre", "nombres", "cliente", "razon social", "full name"],
    "correo":    ["correo", "email", "e-mail", "correo electronico", "mail"],
    "fecha":     ["fecha", "fecha registro", "date", "fecha de creacion"],
}

UMBRAL_DIFUSO = 0.82  # 0..1 — qué tan parecido debe ser un encabezado al sinónimo


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes, solo alfanuméricos: 'Correo Electrónico' -> 'correoelectronico'."""
    if texto is None:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", sin_tildes.lower())


def _parecido(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def detectar_columnas(encabezados: list[str]) -> dict[str, int]:
    """Devuelve {campo_logico: indice_de_columna} detectando por nombre de encabezado."""
    norm_headers = [_normalizar(h) for h in encabezados]
    resultado: dict[str, int] = {}

    for campo, sinonimos in SINONIMOS.items():
        norm_sinonimos = [_normalizar(s) for s in sinonimos]
        mejor_idx, mejor_score = None, 0.0

        for idx, nh in enumerate(norm_headers):
            if not nh or idx in resultado.values():
                continue
            # 1) coincidencia exacta o por contención
            if any(nh == ns or ns in nh or nh in ns for ns in norm_sinonimos):
                mejor_idx, mejor_score = idx, 1.0
                break
            # 2) coincidencia difusa
            score = max(_parecido(nh, ns) for ns in norm_sinonimos)
            if score > mejor_score:
                mejor_idx, mejor_score = idx, score

        if mejor_idx is not None and mejor_score >= UMBRAL_DIFUSO:
            resultado[campo] = mejor_idx

    return resultado


def leer_csv(contenido: str) -> list[dict]:
    """Lee un CSV y devuelve filas como dicts {campo_logico: valor}, sin importar el orden de columnas."""
    filas = list(csv.reader(io.StringIO(contenido)))
    if not filas:
        return []
    encabezados, *datos = filas
    mapa = detectar_columnas(encabezados)

    registros = []
    for fila in datos:
        registro = {}
        for campo, idx in mapa.items():
            registro[campo] = fila[idx].strip() if idx < len(fila) else ""
        registros.append(registro)
    return registros


if __name__ == "__main__":
    # Mismo dato, DOS archivos con columnas en distinto orden y encabezados "sucios".
    archivo_a = (
        "Identificación,Nombre del Cliente,Correo Electrónico,Fecha\n"
        "123456,Ana Gómez,ana@mail.com,2026-01-15\n"
    )
    archivo_b = (
        "e-mail;NOMBRES;fecha registro;Cédula\n"  # otro orden y otros nombres
    ).replace(";", ",") + "luis@mail.com,Luis Pérez,2026-02-01,987654\n"

    print("Archivo A ->", leer_csv(archivo_a))
    print("Archivo B ->", leer_csv(archivo_b))
    # Ambos producen los mismos campos lógicos aunque el orden y los nombres cambien:
    # {'documento': ..., 'nombre': ..., 'correo': ..., 'fecha': ...}
