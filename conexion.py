import streamlit as st
import pandas as pd
from supabase import create_client, Client
import uuid # Necesario para darle nombres únicos a los archivos

# 1. Configuración inicial
st.set_page_config(page_title="Sistema de Documentos", layout="wide")

SUPABASE_URL = "https://pdaixtdkrdxppsefnwqr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkYWl4dGRrcmR4cHBzZWZud3FyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxMzM5OTEsImV4cCI6MjEwMzcwOTk5MX0.pLtb1Qq3etkDh5Rne9xGb2ZKYV9yfzqQuUTkSgXZzTw" 
 # Pon tu llave real aquí

@st.cache_resource
def iniciar_conexion():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = iniciar_conexion()
nombre_tabla = "gestion_documentos" # Asegúrate de que sea tu nombre correcto

st.title("📄 Panel de Control de Documentos")

tab1, tab2, tab3 = st.tabs(["📋 Registro Actual", "➕ Nuevo Documento", "📝 Actualizar Estado"])

# --- PESTAÑA 1: TABLA DE DATOS ---
with tab1:
    st.subheader("Documentos Registrados")
    
    if st.button("🔄 Actualizar Tabla"):
        st.rerun()

    respuesta = supabase.table(nombre_tabla).select("*").execute()
    datos = respuesta.data

    if datos:
        df = pd.DataFrame(datos)
        
        # Hacemos que la tabla sea mucho más visual y los links funcionen
        st.dataframe(
            df, 
            width='stretch',
            column_config={
                "DOCUMENTO": st.column_config.LinkColumn(
                    "Archivo Adjunto", display_text="📄 Ver PDF/Word"
                ),
                "LINK DE RECEPCIÓN": st.column_config.LinkColumn(
                    "Link Recepción", display_text="🔗 Abrir"
                ),
                "LINK DE RESPUESTA": st.column_config.LinkColumn(
                    "Link Respuesta", display_text="🔗 Abrir"
                ),
                "id": st.column_config.NumberColumn(
                    "ID", format="%d" # Quita las comas de los miles en el ID
                )
            },
            hide_index=True # Oculta la columna de números que pone Pandas por defecto
        )
    else:
        st.info("No hay documentos registrados aún.")

# --- PESTAÑA 2: FORMULARIO DE REGISTRO ---
with tab2:
    st.subheader("Registrar Nuevo Documento")
    
    with st.form("formulario_nuevo_doc", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_doc = st.text_input("Tipo de Documento") 
            asunto = st.text_input("Asunto")
            requiere_respuesta = st.radio("¿Requiere Respuesta?", ["SÍ", "NO"])
            derivado_a = st.text_input("Derivado A")
            
        with col2:
            fecha_str = st.date_input("Fecha de Recepción").strftime("%Y-%m-%d") 
            analista = st.text_input("Analista Responsable")
            estado = st.selectbox("Estado Inicial", ["Pendiente", "En Revisión", "Atendido"])
            link = st.text_input("Link de Recepción (URL de Drive/Externa)")

        # NUEVO: Botón para subir archivo
        st.markdown("---")
        archivo_subido = st.file_uploader("Adjuntar Documento (Opcional - PDF, DOCX)", type=["pdf", "doc", "docx"])
        st.markdown("---")

        link_respuesta = st.text_input("Link de Respuesta (URL)")
        observaciones = st.text_area("Observaciones")
        
        enviado = st.form_submit_button("Guardar Documento")
        
        if enviado:
            if asunto and analista: 
                url_archivo_supabase = None
                
                # Si el usuario subió un archivo, lo guardamos en Supabase Storage
                if archivo_subido is not None:
                    # Creamos un nombre único para que no se sobreescriban si se llaman igual
                    extension = archivo_subido.name.split(".")[-1]
                    nombre_unico = f"{uuid.uuid4()}.{extension}"
                    
                    try:
                        # Subimos el archivo al bucket llamado "archivos"
                        supabase.storage.from_("archivos").upload(
                            path=nombre_unico,
                            file=archivo_subido.read(),
                            file_options={"content-type": archivo_subido.type}
                        )
                        # Obtenemos la URL pública para guardarla en la base de datos
                        url_archivo_supabase = supabase.storage.from_("archivos").get_public_url(nombre_unico)
                    except Exception as e:
                        st.error(f"⚠️ El registro se guardará, pero hubo un error subiendo el archivo: {e}")

                # Preparamos los datos para la tabla
                nuevo_registro = {
                    "TIPO DE DOCUMENTO": tipo_doc,
                    "ASUNTO": asunto,
                    "REQUIERE RESPUESTA": requiere_respuesta,
                    "FECHA DE RECEPCIÓN/SALIDA": fecha_str,
                    "ANALISTA RESPONSABLE": analista,
                    "ESTADO ACTUAL": estado,
                    "LINK DE RECEPCIÓN": link,
                    "DERIVADO A": derivado_a,
                    "LINK DE RESPUESTA": link_respuesta, 
                    "OBSERVACIONES": observaciones,
                    "DOCUMENTO": url_archivo_supabase # Aquí guardamos el link del archivo físico
                }
                
                try:
                    respuesta_insert = supabase.table(nombre_tabla).insert(nuevo_registro).execute()
                    st.success("✅ ¡Documento guardado con éxito! Ve a la pestaña 'Registro Actual' para verlo.")
                except Exception as e:
                    st.error(f"❌ Ocurrió un error al guardar en la base de datos: {e}")
            else:
                st.warning("⚠️ Por favor, llena al menos el Asunto y el Analista Responsable.")

# --- PESTAÑA 3: ACTUALIZAR ESTADO ---
with tab3:
    st.subheader("Actualizar Documento Pendiente")
    try:
        pendientes = supabase.table(nombre_tabla).select('id, ASUNTO, "ESTADO ACTUAL"').neq("ESTADO ACTUAL", "Atendido").execute()
        
        if pendientes.data:
            opciones = {f"{doc['ASUNTO']} ({doc['ESTADO ACTUAL']})": doc['id'] for doc in pendientes.data if 'id' in doc}
            
            if opciones:
                doc_seleccionado = st.selectbox("Selecciona el documento a actualizar:", options=list(opciones.keys()))
                id_doc = opciones[doc_seleccionado]
                
                with st.form("form_actualizar"):
                    nuevo_estado = st.selectbox("Nuevo Estado", ["En Revisión", "Atendido"])
                    nuevo_link_resp = st.text_input("Nuevo Link de Respuesta (URL)")
                    nuevas_obs = st.text_area("Agregar Observaciones")
                    
                    if st.form_submit_button("Actualizar Documento"):
                        datos_actualizar = {"ESTADO ACTUAL": nuevo_estado}
                        if nuevo_link_resp:
                            datos_actualizar["LINK DE RESPUESTA"] = nuevo_link_resp
                        if nuevas_obs:
                            datos_actualizar["OBSERVACIONES"] = nuevas_obs
                            
                        supabase.table(nombre_tabla).update(datos_actualizar).eq("id", id_doc).execute()
                        st.success("✅ Documento actualizado.")
        else:
            st.success("🎉 ¡No hay documentos pendientes por atender!")
    except Exception as e:
        st.error(f"Error al cargar pendientes: {e}")