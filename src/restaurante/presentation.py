"""Shared presentation helpers; all business rules remain in the domain services."""

from html import escape
from pathlib import Path

import streamlit as st


def load_styles():
    css = Path(__file__).with_name("interface.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def page_header(section, title, description):
    st.markdown(
        f'<header class="mise-page-header"><p class="mise-eyebrow">{escape(section)}</p>'
        f'<h1>{escape(title)}</h1><p class="mise-description">{escape(description)}</p></header>',
        unsafe_allow_html=True,
    )


def brand():
    st.markdown(
        '<div class="mise-brand"><span class="mise-brand-mark" aria-hidden="true">m.</span>'
        '<div><strong>mise</strong><span>Tu cocina, en orden.</span></div></div>',
        unsafe_allow_html=True,
    )


def context_bar(mode, date_label):
    label = "Espacio de demostración · datos de ejemplo" if mode == "Demostración" else "Mi restaurante"
    st.markdown(
        '<div class="mise-context"><span class="mise-context-label">'
        f'<span class="mise-dot" aria-hidden="true"></span>{escape(label)}</span>'
        f'<span>{escape(date_label)} · Lima</span></div>', unsafe_allow_html=True,
    )


def note(title, description):
    st.markdown(
        f'<aside class="mise-note"><strong>{escape(title)}</strong>'
        f'<p>{escape(description)}</p></aside>', unsafe_allow_html=True,
    )


def welcome():
    st.markdown(
        '<div class="mise-welcome"><div><p class="mise-eyebrow">PARA EL DÍA A DÍA DE TU RESTAURANTE</p>'
        '<h1>Una cocina mejor organizada.</h1>'
        '<p>Controla tus insumos hoy.<br>Compra con más información mañana.</p>'
        '<div class="mise-welcome-tags"><span>Inventario</span><span>Ventas</span>'
        '<span>Plan de compras</span></div></div>'
        '<div class="mise-workflow" aria-label="Cómo funciona">'
        '<div><span>01</span><p><strong>Registra</strong><small>Compras, recetas y ventas.</small></p></div>'
        '<div><span>02</span><p><strong>Controla</strong><small>Stock, vencimientos y mermas.</small></p></div>'
        '<div><span>03</span><p><strong>Planifica</strong><small>Qué necesitas y cuándo comprar.</small></p></div>'
        '</div></div>', unsafe_allow_html=True,
    )
