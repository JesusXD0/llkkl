import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

# CONFIGURACION -------------------------------------------------------------------------------------------------------

TOKEN = os.getenv("TOKEN")

NOMBRE = "Grupo Televisa"
COLOR_TELEVISA = discord.Color.from_rgb(5, 10, 48)       # #050a30
PIE_EMBED = NOMBRE                                       # pie fijo de las tarjetas del /embed

CANAL_BIENVENIDA_ID = 1554327372919079043
CANAL_DESPEDIDA_ID = 1554329826221883503
CANAL_ASCENSOS_ID = 0    # Canal donde se publican ascensos y descensos. 0 = el mismo canal donde se usa el comando

# Zona horaria para la fecha de los ascensos (UTC-7). Cambia el -7 si necesitas otra.
ZONA_HORARIA = timezone(timedelta(hours=-7))

# Jerarquía de MENOR a MAYOR rango (el índice 0 es el más bajo).
JERARQUIA = [
    # Grupo 1 (separador 1)
    1554367147894116372,
    1554365222435819530,
    1554362769787068437,
    1568115709966549135,
    1568115844515496058,
    # Grupo 2 (separador 2)
    1554362784496492575,
    1554362994140516392,
    1554364553746190378,
    1554332161883119616,
    # Grupo 3 (separador 3)
    1554332042366427176,
    1554332105939361832,
    1554331952138682388,
    1554331285483163720,
    # Grupo 4 (separador 4)
    1554331819107946496,
    1554331492761477151,
    1554328960987570217,
    1554324922715865089,
]

# Separadores en el mismo orden de los grupos: grupo 1 (los rangos más bajos) ... grupo 4 (los más altos)
SEPARADORES_RANGO = [
    1554364787624910900,   # separador del grupo 1
    1554365001391804426,   # separador 2
    1554331767496900658,   # separador 3
    1554331200464617513,   # separador 4
]


def indice_grupo(indice_rango: int) -> int:
    """0 = grupo 1 (índices 0-4), 1 = grupo 2 (5-8), 2 = grupo 3 (9-12), 3 = grupo 4 (13-16)."""
    if indice_rango <= 4:
        return 0
    if indice_rango <= 8:
        return 1
    if indice_rango <= 12:
        return 2
    return 3


# UTILIDADES ----------------------------------------------------------------------------------------------------------

def buscar_archivo(nombre: str) -> Optional[str]:
    """Busca un archivo junto a bot.py sin importar mayúsculas/minúsculas (fondo.png, etc.)."""
    carpeta = os.path.dirname(os.path.abspath(__file__))
    for archivo in os.listdir(carpeta):
        if archivo.lower() == nombre.lower():
            return os.path.join(carpeta, archivo)
    return None


def es_imagen(archivo: discord.Attachment) -> bool:
    if archivo.content_type and archivo.content_type.startswith("image/"):
        return True
    return archivo.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))


def extension_archivo(archivo: discord.Attachment) -> str:
    return os.path.splitext(archivo.filename)[1].lower() or ".png"


class ModalBase(discord.ui.Modal):

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f" Error en el formulario: {error!r}")
        if interaction.response.is_done():
            await interaction.followup.send("Ocurrió un error con el formulario.", ephemeral=True)
        else:
            await interaction.response.send_message("Ocurrió un error con el formulario.", ephemeral=True)


intents = discord.Intents.default()
intents.members = True    # Activa "Server Members Intent" en el portal de desarrolladores de Discord

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.CustomActivity(name=f"{NOMBRE} | MXRP"))
    try:
        sincronizados = await bot.tree.sync()
        print(f"Comandos slash sincronizados: {len(sincronizados)}.")
    except Exception as e:
        print(f"Error sincronizando comandos slash: {e!r}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        texto = "No tienes permiso para usar este comando."
    else:
        print(f" Error en un comando: {error!r}")
        texto = "Ocurrió un error al ejecutar el comando."
    if interaction.response.is_done():
        await interaction.followup.send(texto, ephemeral=True)
    else:
        await interaction.response.send_message(texto, ephemeral=True)


# BIENVENIDAS Y DESPEDIDAS --------------------------------------------------------------------------------------------

async def _canal_por_id(canal_id: int):
    canal = bot.get_channel(canal_id)
    if canal is None:
        try:
            canal = await bot.fetch_channel(canal_id)
        except Exception:
            return None
    return canal


async def enviar_tarjeta(canal_id: int, descripcion: str, contenido: Optional[str] = None, ping: bool = False):
    """Tarjeta azul #050a30 con la imagen fondo.png grande abajo."""
    canal = await _canal_por_id(canal_id)
    if canal is None:
        print(f" No encontré el canal {canal_id}.")
        return

    embed = discord.Embed(description=descripcion, color=COLOR_TELEVISA)

    kwargs = {}
    ruta = buscar_archivo("fondo.png")
    if ruta:
        embed.set_image(url="attachment://fondo.png")
        kwargs["file"] = discord.File(ruta, filename="fondo.png")
    else:
        print(" No encontré fondo.png junto a bot.py: el mensaje sale sin imagen.")

    try:
        await canal.send(
            content=contenido,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=ping),
            **kwargs,
        )
    except Exception as e:
        print(f" Error enviando la tarjeta: {e!r}")


@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return
    await enviar_tarjeta(
        CANAL_BIENVENIDA_ID,
        (
            f"**Un nuevo usuario ingresó al servidor.**\n"
            f"# BIENVENIDO {member.mention}\n"
            f"Esperamos que disfrutes tu estancia en **{NOMBRE}**, te invitamos a recibir nuestras "
            f"mejores noticias o ingresar como **Trabajador**."
        ),
        contenido=member.mention,   # la mención va arriba de la tarjeta y le llega al usuario
        ping=True,
    )


@bot.event
async def on_member_remove(member: discord.Member):
    if member.bot:
        return
    await enviar_tarjeta(
        CANAL_DESPEDIDA_ID,
        (
            f"**Un usuario abandonó el servidor.**\n"
            f"# HASTA PRONTO {member.display_name}\n"
            f"Gracias por haber sido parte de **{NOMBRE}**. Te deseamos mucho éxito, "
            f"las puertas siempre estarán abiertas."
        ),
    )


# ASCENSOS Y DESCENSOS ------------------------------------------------------------------------------------------------

def obtener_rango_actual(miembro: discord.Member) -> int:
    """Devuelve el índice más alto de la jerarquía que tiene el miembro, o -1 si no tiene ninguno."""
    ids_miembro = {r.id for r in miembro.roles}
    actual = -1
    for i, rol_id in enumerate(JERARQUIA):
        if rol_id in ids_miembro:
            actual = i
    return actual


async def cambiar_rango(interaction: discord.Interaction, miembro: discord.Member, direccion: int,
                        motivo: str, rango_destino: Optional[int] = None):
    guild = interaction.guild
    autor = interaction.user

    if miembro.bot:
        return await interaction.response.send_message("No puedes cambiar el rango de un bot.", ephemeral=True)
    if miembro == autor:
        return await interaction.response.send_message("No puedes cambiar tu propio rango.", ephemeral=True)

    actual = obtener_rango_actual(miembro)
    if rango_destino is not None:
        # Ascenso o descenso a un rango específico (salta varios rangos de una vez)
        if direccion > 0 and rango_destino <= actual:
            return await interaction.response.send_message(f"{miembro.mention} ya tiene ese rango o uno superior.", ephemeral=True)
        if direccion < 0 and rango_destino >= actual:
            return await interaction.response.send_message(f"{miembro.mention} ya tiene ese rango o uno inferior.", ephemeral=True)
        nuevo = rango_destino
    else:
        nuevo = actual + direccion

    if nuevo >= len(JERARQUIA):
        return await interaction.response.send_message(f"{miembro.mention} ya tiene el rango máximo.", ephemeral=True)
    if nuevo < -1:
        return await interaction.response.send_message(f"{miembro.mention} no tiene ningún rango de la jerarquía.", ephemeral=True)

    rol_actual = guild.get_role(JERARQUIA[actual]) if actual >= 0 else None
    rol_nuevo = guild.get_role(JERARQUIA[nuevo]) if nuevo >= 0 else None

    if (actual >= 0 and rol_actual is None) or (nuevo >= 0 and rol_nuevo is None):
        return await interaction.response.send_message("No encontré uno de los roles de la jerarquía en el servidor.", ephemeral=True)

    # Verificación de jerarquía de Discord
    yo = guild.me
    for rol in (rol_actual, rol_nuevo):
        if rol is None:
            continue
        if rol >= yo.top_role:
            return await interaction.response.send_message(
                f"No puedo gestionar el rol {rol.mention}: está por encima o igual a mi rol más alto.", ephemeral=True
            )
        if autor != guild.owner and rol >= autor.top_role:
            return await interaction.response.send_message(
                f"No puedes gestionar el rol {rol.mention}: está por encima o igual a tu rol más alto.", ephemeral=True
            )

    # Cambiar roles puede tardar más de 3 segundos
    await interaction.response.defer(ephemeral=True)

    try:
        if rol_actual:
            await miembro.remove_roles(rol_actual, reason=f"Cambio de rango por {autor}")
        if rol_nuevo:
            await miembro.add_roles(rol_nuevo, reason=f"Cambio de rango por {autor}")
    except discord.Forbidden:
        return await interaction.followup.send(
            "No pude cambiar el rol. Revisa que el bot tenga **Gestionar roles** y esté por encima de ellos.", ephemeral=True
        )

    # Pone el separador del grupo al que pertenece el nuevo rango y quita los de los otros grupos.
    # Si se queda sin rango (descenso por debajo del más bajo) se quitan todos los separadores.
    grupo = indice_grupo(nuevo) if nuevo >= 0 else None
    separador_nuevo = guild.get_role(SEPARADORES_RANGO[grupo]) if grupo is not None else None
    separadores_viejos = [
        guild.get_role(rol_id) for i, rol_id in enumerate(SEPARADORES_RANGO) if i != grupo
    ]
    separadores_viejos = [r for r in separadores_viejos if r is not None and r in miembro.roles]
    try:
        if separadores_viejos:
            await miembro.remove_roles(*separadores_viejos, reason=f"Cambio de rango por {autor}")
        if separador_nuevo and separador_nuevo not in miembro.roles:
            await miembro.add_roles(separador_nuevo, reason=f"Cambio de rango por {autor}")
    except discord.Forbidden:
        print(f" No pude cambiar los separadores de {miembro}: el rol del bot debe estar por encima de ellos.")

    canal = bot.get_channel(CANAL_ASCENSOS_ID) if CANAL_ASCENSOS_ID else interaction.channel

    if canal is None:
        return await interaction.followup.send(
            "El rango se cambió, pero no encontré el canal de ascensos/descensos.", ephemeral=True
        )

    anterior_txt = rol_actual.mention if rol_actual else "Sin rango"
    nuevo_txt = rol_nuevo.mention if rol_nuevo else "Sin rango"

    if direccion > 0:
        titulo, etiqueta = "ASCENSO", "ascendido"
    else:
        titulo, etiqueta = "DESCENSO", "descendido"

    embed = discord.Embed(
        description=(
            f"# {titulo}\n\n"
            f"**Responsable:**\n{autor.mention}\n\n"
            f"**Usuario {etiqueta}:**\n{miembro.mention}\n\n"
            f"**Cargo anterior:**\n{anterior_txt}\n\n"
            f"**Nuevo cargo:**\n{nuevo_txt}"
        ),
        color=COLOR_TELEVISA,
    )
    embed.add_field(name="Motivo:", value=motivo, inline=True)
    embed.add_field(name="Fecha:", value=datetime.now(ZONA_HORARIA).strftime("%d/%m/%Y"), inline=True)
    embed.set_footer(text=NOMBRE, icon_url=guild.icon.url if guild.icon else None)

    try:
        # Las menciones dentro de un embed se ven pero no dan ping
        await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except Exception as e:
        print(f" Error enviando el aviso de {titulo.lower()}: {e!r}")
        return await interaction.followup.send("El rango se cambió, pero no pude enviar el aviso.", ephemeral=True)

    await interaction.followup.send("Cambio de rango registrado correctamente.", ephemeral=True)


def indice_de_rol(rol: Optional[discord.Role]) -> Optional[int]:
    return JERARQUIA.index(rol.id) if rol is not None and rol.id in JERARQUIA else None


@bot.tree.command(name="ascender", description="Sube de rango a un usuario")
@app_commands.describe(
    usuario="Usuario a ascender",
    motivo="Motivo del ascenso",
    rango="Rango al que sube (opcional, si lo dejas vacío sube 1 rango)",
)
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.guild_only()
async def ascender(interaction: discord.Interaction, usuario: discord.Member,
                   motivo: app_commands.Range[str, 1, 500], rango: Optional[discord.Role] = None):
    indice = None
    if rango is not None:
        indice = indice_de_rol(rango)
        if indice is None:
            return await interaction.response.send_message("Ese rol no forma parte de la jerarquía.", ephemeral=True)
    await cambiar_rango(interaction, usuario, +1, motivo, indice)


@bot.tree.command(name="descender", description="Baja de rango a un usuario")
@app_commands.describe(
    usuario="Usuario a descender",
    motivo="Motivo del descenso",
    rango="Rango al que baja (opcional, si lo dejas vacío baja 1 rango)",
)
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.guild_only()
async def descender(interaction: discord.Interaction, usuario: discord.Member,
                    motivo: app_commands.Range[str, 1, 500], rango: Optional[discord.Role] = None):
    indice = None
    if rango is not None:
        indice = indice_de_rol(rango)
        if indice is None:
            return await interaction.response.send_message("Ese rol no forma parte de la jerarquía.", ephemeral=True)
    await cambiar_rango(interaction, usuario, -1, motivo, indice)


# NOTICIAS ------------------------------------------------------------------------------------------------------------

@bot.tree.command(name="noticia", description="Publica una noticia de Grupo Televisa")
@app_commands.describe(
    titular="Titular de la noticia",
    contenido="Texto de la noticia",
    imagen="Imagen de la noticia (opcional)",
    canal="Canal donde se publica (si lo dejas vacío, este mismo canal)",
    ping="Rol al que se menciona (opcional)",
)
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.guild_only()
async def noticia(
    interaction: discord.Interaction,
    titular: app_commands.Range[str, 1, 200],
    contenido: app_commands.Range[str, 1, 1800],
    imagen: Optional[discord.Attachment] = None,
    canal: Optional[discord.TextChannel] = None,
    ping: Optional[discord.Role] = None,
):
    destino = canal or interaction.channel

    if imagen is not None:
        if not es_imagen(imagen):
            return await interaction.response.send_message("El archivo debe ser una imagen o GIF.", ephemeral=True)
        if imagen.size > interaction.guild.filesize_limit:
            return await interaction.response.send_message(
                "El archivo pesa más de lo que permite este servidor para subir archivos.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        description=f"**🔴 ÚLTIMA HORA**\n# {titular}\n{contenido}",
        color=COLOR_TELEVISA,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"{NOMBRE} · Noticias", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    kwargs = {}
    if imagen is not None:
        nombre = f"noticia{extension_archivo(imagen)}"
        kwargs["file"] = await imagen.to_file(filename=nombre)
        embed.set_image(url=f"attachment://{nombre}")

    try:
        mensaje = await destino.send(
            content=ping.mention if ping else None,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=[discord.Object(id=ping.id)], users=False) if ping
            else discord.AllowedMentions.none(),
            **kwargs,
        )
    except Exception as e:
        print(f" Error publicando la noticia: {e!r}")
        return await interaction.followup.send(f"No pude publicar la noticia. Error: `{type(e).__name__}: {e}`", ephemeral=True)

    await interaction.followup.send(f"Noticia publicada: {mensaje.jump_url}", ephemeral=True)


# GENERADOR DE EMBEDS (/embed) ----------------------------------------------------------------------------------------
#
# /embed abre un editor privado (solo lo ves tú) con vista previa en vivo.
#  - Cada cambio se guarda solo: puedes cerrar el editor y al volver a usar /embed carga lo último que tenías.
#  - Cada persona tiene su propio borrador.
#  - El pie de la tarjeta SIEMPRE lleva el nombre del grupo.
#  - Los borradores se guardan en un archivo JSON. En Railway el disco se borra en cada deploy: si quieres que
#    sobrevivan, crea un Volume y pon la variable DATA_DIR con su ruta (ejemplo: /data).

CARPETA_DATOS = os.getenv("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
RUTA_BORRADORES = os.path.join(CARPETA_DATOS, "embeds_borradores.json")
CARPETA_IMAGENES_EMBED = os.path.join(CARPETA_DATOS, "embed_imagenes")

MAX_PINGS_EMBED = 10


def cargar_borradores() -> dict:
    try:
        with open(RUTA_BORRADORES, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f" No pude leer los borradores de embeds: {e}")
        return {}


BORRADORES: dict = cargar_borradores()


def guardar_borradores():
    try:
        os.makedirs(CARPETA_DATOS, exist_ok=True)
        tmp = RUTA_BORRADORES + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(BORRADORES, f, ensure_ascii=False, indent=1)
        os.replace(tmp, RUTA_BORRADORES)
    except Exception as e:
        print(f" No pude guardar los borradores de embeds: {e}")


MAX_BLOQUES_V2 = 8
LIMITE_TEXTO_V2 = 3900   # Discord permite 4000 caracteres de texto en total por mensaje
COLORES_V2 = {
    "televisa": ("Televisa (azul)", COLOR_TELEVISA),
    "negro": ("Negro", discord.Color.from_rgb(15, 15, 15)),
    "dorado": ("Dorado #9c723d", discord.Color.from_rgb(156, 114, 61)),
    "rojo": ("Rojo", discord.Color.from_rgb(221, 46, 68)),
    "verde": ("Verde", discord.Color.from_rgb(120, 177, 89)),
    "azul": ("Azul", discord.Color.from_rgb(29, 122, 252)),
    "morado": ("Morado", discord.Color.from_rgb(155, 93, 229)),
    "gris": ("Gris", discord.Color.from_rgb(70, 72, 78)),
}


def obtener_borrador(usuario_id: int) -> dict:
    b = BORRADORES.setdefault(str(usuario_id), {})
    b.setdefault("arriba", "")      # texto FUERA de la tarjeta, arriba (aquí también van los pings)
    b.setdefault("abajo", "")       # texto FUERA de la tarjeta, abajo
    b.setdefault("color", "televisa")
    b.setdefault("ping", [])        # ["<@123>", "<@&456>"]
    b.setdefault("bloques", [])     # [{"t": "texto", "v": str} | {"t": "sep"} | {"t": "img", "items": [...]}]
    return b


def borrar_archivo_imagen(datos: Optional[dict]):
    if datos and datos.get("tipo") == "archivo":
        try:
            os.remove(datos.get("ruta", ""))
        except Exception:
            pass


def borrar_archivos_bloque(bloque: dict):
    for item in bloque.get("items", []):
        borrar_archivo_imagen(item)


def texto_arriba(b: dict) -> str:
    return "\n".join(x for x in (" ".join(b["ping"]), (b["arriba"] or "").strip()) if x)


def total_texto_borrador(b: dict) -> int:
    total = len(f"-# {PIE_EMBED}") + len(texto_arriba(b)) + len((b["abajo"] or "").strip())
    return total + sum(len(blq.get("v", "")) for blq in b["bloques"] if blq["t"] == "texto")


def hay_contenido_v2(b: dict) -> bool:
    return bool(b["bloques"] or b["arriba"].strip() or b["abajo"].strip())


def componentes_borrador(b: dict):
    """Arma los componentes de la tarjeta. Devuelve (componentes de nivel superior, archivos a subir)."""
    color = COLORES_V2.get(b.get("color"), COLORES_V2["televisa"])[1]
    items = []
    files = []

    arriba = texto_arriba(b)
    if arriba:
        items.append(discord.ui.TextDisplay(arriba))

    contenedor = discord.ui.Container(accent_colour=color)
    for bloque in b["bloques"]:
        if bloque["t"] == "texto":
            contenedor.add_item(discord.ui.TextDisplay(bloque.get("v") or "\u200b"))
        elif bloque["t"] == "sep":
            contenedor.add_item(discord.ui.Separator())
        elif bloque["t"] == "img":
            galeria = []
            for item in bloque.get("items", []):
                if item.get("tipo") == "url":
                    galeria.append(discord.MediaGalleryItem(item["valor"]))
                elif item.get("tipo") == "archivo" and os.path.isfile(item.get("ruta", "")):
                    nombre = os.path.basename(item["ruta"])
                    files.append(discord.File(item["ruta"], filename=nombre))
                    galeria.append(discord.MediaGalleryItem(f"attachment://{nombre}"))
            if galeria:
                contenedor.add_item(discord.ui.MediaGallery(*galeria))

    # El pie SIEMPRE lleva el nombre del grupo
    contenedor.add_item(discord.ui.Separator())
    contenedor.add_item(discord.ui.TextDisplay(f"-# {PIE_EMBED}"))
    items.append(contenedor)

    abajo = (b["abajo"] or "").strip()
    if abajo:
        items.append(discord.ui.TextDisplay(abajo))

    return items, files


def resumen_bloque(indice: int, bloque: dict) -> str:
    if bloque["t"] == "texto":
        texto = " ".join((bloque.get("v") or "").split())
        return f"{indice + 1}. Texto · {texto[:70] or '(vacío)'}"
    if bloque["t"] == "sep":
        return f"{indice + 1}. Separador"
    return f"{indice + 1}. Imágenes ({len(bloque.get('items', []))})"


# ---------- Ventanas (modales) del editor ----------

class TextoFueraModal(ModalBase):

    texto = discord.ui.Label(
        text="Texto",
        description="Va FUERA de la tarjeta. Admite markdown y menciones. Déjalo vacío para quitarlo.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Texto de fuera...",
            max_length=1500,
            required=False,
        ),
    )

    def __init__(self, vista: "EditorV2View", donde: str):
        super().__init__(title="Texto de arriba (fuera)" if donde == "arriba" else "Texto de abajo (fuera)")
        self.vista = vista
        self.donde = donde
        self.texto.component.default = vista.borrador[donde] or None

    async def on_submit(self, interaction: discord.Interaction):
        self.vista.borrador[self.donde] = (self.texto.component.value or "").strip()
        guardar_borradores()
        await self.vista.refrescar(interaction)


class BloqueTextoModal(ModalBase):

    texto = discord.ui.Label(
        text="Texto dentro de la tarjeta",
        description="Markdown: # título, ## sub, **negrita**, *cursiva*, > cita, -# pequeño, <@id> menciones",
        component=discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="# TÍTULO\n**Negritas**, > citas, listas, emojis...",
            max_length=3000,
        ),
    )

    def __init__(self, vista: "EditorV2View", indice: Optional[int] = None):
        super().__init__(title="Texto de la tarjeta" if indice is None else f"Editar bloque {indice + 1}")
        self.vista = vista
        self.indice = indice
        if indice is not None:
            self.texto.component.default = vista.borrador["bloques"][indice].get("v") or None

    async def on_submit(self, interaction: discord.Interaction):
        b = self.vista.borrador
        texto = self.texto.component.value.strip()
        if self.indice is None:
            if len(b["bloques"]) >= MAX_BLOQUES_V2:
                return await interaction.response.send_message(f"Máximo {MAX_BLOQUES_V2} bloques.", ephemeral=True)
            b["bloques"].append({"t": "texto", "v": texto})
            self.vista.sel = len(b["bloques"]) - 1
        else:
            b["bloques"][self.indice]["v"] = texto
        guardar_borradores()
        await self.vista.refrescar(interaction)


class BloqueImagenModal(ModalBase):

    link = discord.ui.Label(
        text="Link de la imagen (opcional)",
        description="Puedes poner un link y/o subir archivos.",
        component=discord.ui.TextInput(
            placeholder="https://...",
            max_length=500,
            required=False,
        ),
    )

    archivos = discord.ui.Label(
        text="Archivos (opcional)",
        description="Hasta 4 imágenes o GIFs. Se muestran juntos como galería dentro de la tarjeta.",
        component=discord.ui.FileUpload(
            min_values=0,
            max_values=4,
            required=False,
        ),
    )

    def __init__(self, vista: "EditorV2View", indice: Optional[int] = None):
        super().__init__(title="Imágenes de la tarjeta" if indice is None else f"Cambiar imágenes del bloque {indice + 1}")
        self.vista = vista
        self.indice = indice

    async def on_submit(self, interaction: discord.Interaction):
        b = self.vista.borrador
        link = (self.link.component.value or "").strip()
        adjuntos = list(self.archivos.component.values or [])

        if self.indice is None and len(b["bloques"]) >= MAX_BLOQUES_V2:
            return await interaction.response.send_message(f"Máximo {MAX_BLOQUES_V2} bloques.", ephemeral=True)

        items = []
        if link:
            if not link.lower().startswith(("http://", "https://")):
                return await interaction.response.send_message("El link debe empezar con http:// o https://", ephemeral=True)
            items.append({"tipo": "url", "valor": link})

        for a in adjuntos:
            if not es_imagen(a):
                return await interaction.response.send_message("Los archivos deben ser imágenes o GIFs.", ephemeral=True)
            if a.size > 8 * 1024 * 1024:
                return await interaction.response.send_message("Una imagen pesa más de 8 MB.", ephemeral=True)

        guardados = []
        try:
            os.makedirs(CARPETA_IMAGENES_EMBED, exist_ok=True)
            for a in adjuntos:
                contenido = await a.read()
                ruta = os.path.join(CARPETA_IMAGENES_EMBED, f"{interaction.user.id}_{secrets.token_hex(4)}{extension_archivo(a)}")
                with open(ruta, "wb") as f:
                    f.write(contenido)
                guardados.append({"tipo": "archivo", "ruta": ruta})
        except Exception as e:
            print(f" Error guardando las imágenes del embed: {e}")
            for item in guardados:
                borrar_archivo_imagen(item)
            return await interaction.response.send_message("No pude guardar las imágenes.", ephemeral=True)
        items += guardados

        if not items:
            if self.indice is None:
                return await interaction.response.send_message("Pon un link o sube al menos una imagen.", ephemeral=True)
            return await self.vista.refrescar(interaction)   # editar sin cambios

        if self.indice is None:
            b["bloques"].append({"t": "img", "items": items})
            self.vista.sel = len(b["bloques"]) - 1
        else:
            borrar_archivos_bloque(b["bloques"][self.indice])
            b["bloques"][self.indice] = {"t": "img", "items": items}
        guardar_borradores()
        await self.vista.refrescar(interaction)


class PingV2Modal(ModalBase, title="Ping del mensaje"):

    menciones = discord.ui.Label(
        text="¿A quién mencionar?",
        description="Se mencionan arriba de la tarjeta al enviarla. Vacío = sin ping.",
        component=discord.ui.MentionableSelect(
            placeholder="Usuarios y/o roles",
            min_values=0,
            max_values=MAX_PINGS_EMBED,
            required=False,
        ),
    )

    def __init__(self, vista: "EditorV2View"):
        super().__init__()
        self.vista = vista

    async def on_submit(self, interaction: discord.Interaction):
        self.vista.borrador["ping"] = [m.mention for m in (self.menciones.component.values or [])]
        guardar_borradores()
        await self.vista.refrescar(interaction)


# ---------- Cargar un mensaje en el editor ----------
# Copia texto exterior, bloques, separadores, imágenes y el color más cercano. Los botones no se copian.

def _tipo_componente(c) -> str:
    return getattr(getattr(c, "type", None), "name", "") or ""


def _color_mas_cercano(color) -> str:
    if color is None:
        return "televisa"
    return min(
        COLORES_V2.items(),
        key=lambda kv: (
            (kv[1][1].r - color.r) ** 2
            + (kv[1][1].g - color.g) ** 2
            + (kv[1][1].b - color.b) ** 2
        ),
    )[0]


def _urls_galeria(componente) -> list:
    urls = []
    for item in getattr(componente, "items", None) or []:
        media = getattr(item, "media", None)
        url = (
            getattr(media, "url", None)
            or getattr(item, "url", None)
            or (media if isinstance(media, str) else None)
        )
        if url:
            urls.append(str(url))
    return urls


def _piezas_hijos(hijos, avisos: list) -> list:
    """Convierte hijos de una tarjeta en piezas de texto, separador e imágenes."""
    piezas = []
    for hijo in hijos or []:
        tipo = _tipo_componente(hijo)
        contenido = getattr(hijo, "content", None)

        if isinstance(contenido, str):
            if contenido.strip():
                piezas.append(("texto", contenido))
        elif tipo == "separator":
            piezas.append(("sep",))
        elif tipo == "media_gallery":
            urls = _urls_galeria(hijo)
            if urls:
                piezas.append(("img", urls))
        elif tipo == "section":
            # Se copia el texto de la sección; accesorios como miniaturas no son editables aquí.
            piezas.extend(
                p for p in _piezas_hijos(getattr(hijo, "children", None), avisos)
                if p[0] == "texto"
            )
        elif tipo == "action_row":
            aviso = "Los botones no se copian."
            if aviso not in avisos:
                avisos.append(aviso)
    return piezas


def _unir_imagenes(piezas: list) -> list:
    """Agrupa galerías consecutivas para no desperdiciar bloques del editor."""
    resultado = []
    for pieza in piezas:
        if pieza[0] == "img" and resultado and resultado[-1][0] == "img":
            resultado[-1] = ("img", resultado[-1][1] + pieza[1])
        else:
            resultado.append(pieza)
    return resultado


def piezas_de_mensaje(mensaje: discord.Message):
    """Devuelve texto superior, texto inferior, piezas internas, color y avisos."""
    avisos = []
    arriba, abajo, dentro = [], [], []
    color = None

    if getattr(mensaje.flags, "components_v2", False):
        componentes = list(mensaje.components or [])
        hay_contenedor = any(_tipo_componente(c) == "container" for c in componentes)
        visto_contenedor = False

        for componente in componentes:
            tipo = _tipo_componente(componente)
            if tipo == "container":
                visto_contenedor = True
                color = (
                    getattr(componente, "accent_colour", None)
                    or getattr(componente, "accent_color", None)
                )
                dentro.extend(
                    _piezas_hijos(getattr(componente, "children", None), avisos)
                )
            elif hay_contenedor:
                contenido = getattr(componente, "content", None)
                if isinstance(contenido, str) and contenido.strip():
                    (abajo if visto_contenedor else arriba).append(contenido)
                elif tipo == "action_row":
                    aviso = "Los botones no se copian."
                    if aviso not in avisos:
                        avisos.append(aviso)
            else:
                dentro.extend(_piezas_hijos([componente], avisos))

    elif mensaje.embeds:
        if mensaje.content:
            arriba.append(mensaje.content)
        for embed in mensaje.embeds:
            if embed.title:
                dentro.append(("texto", f"## {embed.title}"))
            if embed.description:
                dentro.append(("texto", embed.description))
            if embed.fields:
                texto_campos = "\n\n".join(
                    f"**{campo.name}**\n{campo.value}" for campo in embed.fields
                )
                dentro.append(("texto", texto_campos))
            if embed.image and embed.image.url:
                dentro.append(("img", [embed.image.url]))
            if embed.thumbnail and embed.thumbnail.url:
                dentro.append(("img", [embed.thumbnail.url]))
            if embed.footer and embed.footer.text and PIE_EMBED not in embed.footer.text:
                dentro.append(("texto", f"-# {embed.footer.text}"))
            if embed.colour:
                color = embed.colour
        if mensaje.components:
            avisos.append("Los botones no se copian.")

    elif mensaje.content:
        dentro.append(("texto", mensaje.content))

    # El pie propio del editor no se duplica al volver a cargar una tarjeta.
    if (
        len(dentro) >= 2
        and dentro[-1][0] == "texto"
        and dentro[-1][1].lstrip().startswith("-#")
        and PIE_EMBED in dentro[-1][1]
        and dentro[-2][0] == "sep"
    ):
        dentro = dentro[:-2]

    return (
        "\n".join(arriba)[:1500],
        "\n".join(abajo)[:1500],
        _unir_imagenes(dentro),
        _color_mas_cercano(color),
        avisos,
    )


async def _guardar_imagen_cargada(url: str, adjuntos: dict, uid: int) -> dict:
    """Descarga adjuntos del mensaje; conserva como URL las imágenes externas."""
    import urllib.parse

    nombre = os.path.basename(urllib.parse.urlparse(url).path)
    adjunto = adjuntos.get(nombre)
    if adjunto is not None and adjunto.size <= 8 * 1024 * 1024:
        try:
            contenido = await adjunto.read()
            os.makedirs(CARPETA_IMAGENES_EMBED, exist_ok=True)
            ruta = os.path.join(
                CARPETA_IMAGENES_EMBED,
                f"{uid}_{secrets.token_hex(4)}{extension_archivo(adjunto)}",
            )
            with open(ruta, "wb") as archivo:
                archivo.write(contenido)
            return {"tipo": "archivo", "ruta": ruta}
        except Exception as error:
            print(f"No pude descargar la imagen del mensaje cargado: {error!r}")
    return {"tipo": "url", "valor": url}


class CargarMensajeModal(ModalBase, title="Cargar un mensaje"):
    enlace = discord.ui.Label(
        text="Link o ID del mensaje",
        description="Clic derecho al mensaje > Copiar enlace. Reemplazará tu borrador actual.",
        component=discord.ui.TextInput(
            placeholder="https://discord.com/channels/...",
            max_length=200,
        ),
    )

    def __init__(self, vista: "EditorV2View"):
        super().__init__()
        self.vista = vista

    async def on_submit(self, interaction: discord.Interaction):
        texto = self.enlace.component.value.strip()
        coincidencia = re.search(r"channels/(\d+)/(\d+)/(\d+)", texto)

        if coincidencia:
            if int(coincidencia.group(1)) != interaction.guild_id:
                return await interaction.response.send_message(
                    "Solo puedo cargar mensajes de este servidor.", ephemeral=True
                )
            canal_id = int(coincidencia.group(2))
            mensaje_id = int(coincidencia.group(3))
        elif texto.isdigit():
            canal_id = interaction.channel_id
            mensaje_id = int(texto)
        else:
            return await interaction.response.send_message(
                "Pega el enlace del mensaje o su ID.", ephemeral=True
            )

        await interaction.response.defer()

        canal = interaction.guild.get_channel_or_thread(canal_id)
        if canal is None:
            try:
                canal = await bot.fetch_channel(canal_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return await interaction.followup.send(
                    "No encontré ese canal o no puedo acceder a él.", ephemeral=True
                )

        if not hasattr(canal, "fetch_message") or not hasattr(canal, "permissions_for"):
            return await interaction.followup.send(
                "Ese destino no permite leer mensajes.", ephemeral=True
            )

        permisos_usuario = canal.permissions_for(interaction.user)
        if not (permisos_usuario.view_channel and permisos_usuario.read_message_history):
            return await interaction.followup.send(
                "No tienes permiso para leer el historial de ese canal.", ephemeral=True
            )

        permisos_bot = canal.permissions_for(interaction.guild.me)
        if not (permisos_bot.view_channel and permisos_bot.read_message_history):
            return await interaction.followup.send(
                "Necesito los permisos **Ver canal** y **Leer historial de mensajes** "
                "en el canal del mensaje.", ephemeral=True
            )

        try:
            mensaje = await canal.fetch_message(mensaje_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return await interaction.followup.send(
                "No encontré ese mensaje o no tengo permiso para leerlo.", ephemeral=True
            )

        arriba, abajo, piezas, color, avisos = piezas_de_mensaje(mensaje)
        if not (arriba or abajo or piezas):
            return await interaction.followup.send(
                "Ese mensaje no tiene contenido compatible para cargar.", ephemeral=True
            )

        adjuntos = {adjunto.filename: adjunto for adjunto in mensaje.attachments}
        bloques = []
        for pieza in piezas:
            if len(bloques) >= MAX_BLOQUES_V2:
                avisos.append(f"Solo se cargaron los primeros {MAX_BLOQUES_V2} bloques.")
                break
            if pieza[0] == "texto":
                bloques.append({"t": "texto", "v": pieza[1][:3000]})
            elif pieza[0] == "sep":
                bloques.append({"t": "sep"})
            elif pieza[0] == "img":
                items = [
                    await _guardar_imagen_cargada(url, adjuntos, interaction.user.id)
                    for url in pieza[1][:10]
                ]
                bloques.append({"t": "img", "items": items})

        borrador = obtener_borrador(interaction.user.id)
        for bloque_anterior in borrador["bloques"]:
            borrar_archivos_bloque(bloque_anterior)

        borrador["arriba"] = arriba
        borrador["abajo"] = abajo
        borrador["color"] = color
        borrador["ping"] = []
        borrador["bloques"] = bloques
        guardar_borradores()

        self.vista.stop()
        nueva = EditorV2View(
            self.vista.autor_id,
            self.vista.canal,
            None,
            self.vista.nombre_publicacion,
        )
        await interaction.edit_original_response(view=nueva, attachments=nueva.files)
        mensaje_aviso = "Mensaje cargado en tu borrador."
        if avisos:
            mensaje_aviso += " " + " ".join(dict.fromkeys(avisos))
        await interaction.followup.send(mensaje_aviso, ephemeral=True)


class TituloPublicacionModal(discord.ui.Modal, title="Nueva publicación del foro"):

    nombre = discord.ui.TextInput(
        label="Título de la publicación",
        placeholder="Ej. Información importante",
        max_length=100,
        required=True,
    )

    def __init__(self, autor_id: int, canal):
        super().__init__()
        self.autor_id = autor_id
        self.canal = canal

    async def on_submit(self, interaction: discord.Interaction):
        titulo = self.nombre.value.strip()

        vista = EditorV2View(
            self.autor_id,
            self.canal,
            nombre_publicacion=titulo
        )

        await interaction.response.send_message(
            view=vista,
            files=vista.files,
            ephemeral=True
        )


# ---------- Editor ----------
# Compatible con canales de texto y canales de foro.

class EditorV2View(discord.ui.LayoutView):

    def __init__(
        self,
        autor_id: int,
        canal,
        seleccionado: Optional[int] = None,
        nombre_publicacion: Optional[str] = None
    ):
        super().__init__(timeout=1800)

        self.autor_id = autor_id
        self.canal = canal
        self.nombre_publicacion = nombre_publicacion

        b = self.borrador
        self.sel = seleccionado if seleccionado is not None and 0 <= seleccionado < len(b["bloques"]) else None

        items, self.files = componentes_borrador(b)

        self.add_item(discord.ui.TextDisplay(self.encabezado()))
        self.add_item(discord.ui.Separator())

        for item in items:
            self.add_item(item)

        self.add_item(discord.ui.Separator())

        # Color
        actual = b.get("color", "televisa")

        color = discord.ui.Select(
            placeholder="Color de la tarjeta",
            options=[
                discord.SelectOption(label=n, value=k, default=(k == actual))
                for k, (n, _) in COLORES_V2.items()
            ],
        )

        color.callback = self.cb_color
        self.add_item(self._fila([color]))

        # Selector de bloques
        if b["bloques"]:
            bloque = discord.ui.Select(
                placeholder="Selecciona un bloque para editarlo, moverlo o quitarlo",
                options=[
                    discord.SelectOption(
                        label=resumen_bloque(i, blq)[:100],
                        value=str(i),
                        default=(i == self.sel)
                    )
                    for i, blq in enumerate(b["bloques"])
                ],
            )

            bloque.callback = self.cb_bloque
            self.add_item(self._fila([bloque]))

        lleno = len(b["bloques"]) >= MAX_BLOQUES_V2
        sin_sel = self.sel is None

        self.add_item(self._fila([
            self._boton("Texto arriba", "⬆️", discord.ButtonStyle.secondary, self.cb_arriba),
            self._boton("Texto abajo", "⬇️", discord.ButtonStyle.secondary, self.cb_abajo),
            self._boton("+ Texto", "📝", discord.ButtonStyle.primary, self.cb_add_texto, lleno),
            self._boton("+ Imágenes", "🖼️", discord.ButtonStyle.primary, self.cb_add_img, lleno),
            self._boton("+ Separador", "➖", discord.ButtonStyle.primary, self.cb_add_sep, lleno),
        ]))

        self.add_item(self._fila([
            self._boton("Editar", "✏️", discord.ButtonStyle.secondary, self.cb_editar, sin_sel),
            self._boton("Quitar", "🗑️", discord.ButtonStyle.secondary, self.cb_quitar, sin_sel),
            self._boton("Subir", "🔼", discord.ButtonStyle.secondary, self.cb_subir, sin_sel or self.sel == 0),
            self._boton("Bajar", "🔽", discord.ButtonStyle.secondary, self.cb_bajar,
                        sin_sel or self.sel == len(b["bloques"]) - 1),
            self._boton("Ping", "🔔", discord.ButtonStyle.secondary, self.cb_ping),
        ]))

        self.add_item(self._fila([
            self._boton("Enviar", "📨", discord.ButtonStyle.success, self.cb_enviar),
            self._boton("Guardar y salir", "💾", discord.ButtonStyle.secondary, self.cb_salir),
            self._boton("Borrar borrador", "⚠️", discord.ButtonStyle.danger, self.cb_borrar),
            self._boton("Cargar mensaje", "📥", discord.ButtonStyle.primary, self.cb_cargar),
        ]))

    @property
    def borrador(self) -> dict:
        return obtener_borrador(self.autor_id)

    @staticmethod
    def _fila(componentes: list) -> discord.ui.ActionRow:
        fila = discord.ui.ActionRow()
        for c in componentes:
            fila.add_item(c)
        return fila

    @staticmethod
    def _boton(etiqueta, emoji, estilo, callback, desactivado: bool = False):
        boton = discord.ui.Button(
            label=etiqueta,
            emoji=emoji,
            style=estilo,
            disabled=desactivado
        )
        boton.callback = callback
        return boton

    def encabezado(self) -> str:
        b = self.borrador
        total = total_texto_borrador(b)

        aviso = (
            f"\n⚠️ Demasiado texto ({total}/{LIMITE_TEXTO_V2}): acórtalo para poder enviar."
            if total > LIMITE_TEXTO_V2 else ""
        )

        vacio = "" if hay_contenido_v2(b) else "\n⚠️ Está vacío: usa **+ Texto** para empezar."

        return (
            f"**Editor de tarjeta** · Se enviará en {self.canal.mention}\n"
            f"-# Bloques {len(b['bloques'])}/{MAX_BLOQUES_V2} · Texto {total}/{LIMITE_TEXTO_V2} · "
            f"Todo se guarda solo; usa /embed para continuar después.{aviso}{vacio}"
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Este editor es de otra persona.",
                ephemeral=True
            )
            return False

        return True

    async def refrescar(self, interaction: discord.Interaction):
        nueva = EditorV2View(
            self.autor_id,
            self.canal,
            self.sel,
            self.nombre_publicacion
        )

        self.stop()

        await interaction.response.edit_message(
            view=nueva,
            attachments=nueva.files,
            allowed_mentions=discord.AllowedMentions.none()
        )

    # ---------- CALLBACKS ----------

    async def cb_color(self, interaction: discord.Interaction):
        self.borrador["color"] = interaction.data["values"][0]
        guardar_borradores()
        await self.refrescar(interaction)

    async def cb_bloque(self, interaction: discord.Interaction):
        self.sel = int(interaction.data["values"][0])
        await self.refrescar(interaction)

    async def cb_arriba(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextoFueraModal(self, "arriba"))

    async def cb_abajo(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextoFueraModal(self, "abajo"))

    async def cb_add_texto(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BloqueTextoModal(self))

    async def cb_add_img(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BloqueImagenModal(self))

    async def cb_add_sep(self, interaction: discord.Interaction):
        b = self.borrador

        if len(b["bloques"]) >= MAX_BLOQUES_V2:
            return await interaction.response.send_message(
                f"Máximo {MAX_BLOQUES_V2} bloques.",
                ephemeral=True
            )

        b["bloques"].append({"t": "sep"})
        self.sel = len(b["bloques"]) - 1

        guardar_borradores()
        await self.refrescar(interaction)

    async def cb_editar(self, interaction: discord.Interaction):
        bloque = self.borrador["bloques"][self.sel]

        if bloque["t"] == "texto":
            return await interaction.response.send_modal(
                BloqueTextoModal(self, self.sel)
            )

        if bloque["t"] == "img":
            return await interaction.response.send_modal(
                BloqueImagenModal(self, self.sel)
            )

        await interaction.response.send_message(
            "Un separador no tiene nada que editar: quítalo o muévelo.",
            ephemeral=True
        )

    async def cb_quitar(self, interaction: discord.Interaction):
        b = self.borrador
        borrar_archivos_bloque(b["bloques"].pop(self.sel))

        self.sel = None
        guardar_borradores()

        await self.refrescar(interaction)

    async def cb_subir(self, interaction: discord.Interaction):
        bloques = self.borrador["bloques"]

        bloques[self.sel - 1], bloques[self.sel] = (
            bloques[self.sel],
            bloques[self.sel - 1]
        )

        self.sel -= 1
        guardar_borradores()

        await self.refrescar(interaction)

    async def cb_bajar(self, interaction: discord.Interaction):
        bloques = self.borrador["bloques"]

        bloques[self.sel + 1], bloques[self.sel] = (
            bloques[self.sel],
            bloques[self.sel + 1]
        )

        self.sel += 1
        guardar_borradores()

        await self.refrescar(interaction)

    async def cb_ping(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PingV2Modal(self))

    # ---------- ENVIAR TARJETA ----------

    async def cb_enviar(self, interaction: discord.Interaction):
        b = self.borrador

        if not hay_contenido_v2(b):
            return await interaction.response.send_message(
                "Tu tarjeta está vacía. Agrega texto o una imagen.",
                ephemeral=True
            )

        if total_texto_borrador(b) > LIMITE_TEXTO_V2:
            return await interaction.response.send_message(
                f"Tienes demasiado texto (máximo {LIMITE_TEXTO_V2} caracteres).",
                ephemeral=True
            )

        permisos = self.canal.permissions_for(interaction.guild.me)

        if not permisos.view_channel:
            return await interaction.response.send_message(
                "No tengo permiso para ver ese canal.",
                ephemeral=True
            )

        if isinstance(self.canal, discord.ForumChannel):
            if not permisos.create_public_threads or not permisos.send_messages_in_threads:
                return await interaction.response.send_message(
                    "Necesito los permisos **Crear publicaciones** y **Enviar mensajes en publicaciones** en ese foro.",
                    ephemeral=True
                )
        elif not permisos.send_messages:
            return await interaction.response.send_message(
                "No tengo permiso para enviar mensajes en ese canal.",
                ephemeral=True
            )

        if isinstance(self.canal, discord.ForumChannel) and not self.nombre_publicacion:
            return await interaction.response.send_message(
                "No se indicó el título de la publicación. Ejecuta /embed nuevamente.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        items, files = componentes_borrador(b)

        vista = discord.ui.LayoutView(timeout=None)

        for item in items:
            vista.add_item(item)

        try:
            if isinstance(self.canal, discord.ForumChannel):

                resultado = await self.canal.create_thread(
                    name=self.nombre_publicacion,
                    view=vista,
                    files=files,
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=True,
                        everyone=False
                    )
                )

                enlace = resultado.thread.jump_url

            else:

                mensaje = await self.canal.send(
                    view=vista,
                    files=files,
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=True,
                        everyone=False
                    )
                )

                enlace = mensaje.jump_url

        except Exception as e:
            print(f"Error enviando la tarjeta personalizada: {e!r}")

            return await interaction.followup.send(
                f"No pude enviar la tarjeta. Error: `{type(e).__name__}: {e}`",
                ephemeral=True
            )

        await interaction.followup.send(
            f"Tarjeta publicada correctamente: {enlace}\n"
            "Tu borrador sigue guardado por si quieres reutilizarlo.",
            ephemeral=True
        )

    async def cb_salir(self, interaction: discord.Interaction):
        guardar_borradores()

        vista = discord.ui.LayoutView()
        vista.add_item(
            discord.ui.TextDisplay(
                "Borrador guardado. Usa **/embed** cuando quieras continuar donde lo dejaste."
            )
        )

        self.stop()

        await interaction.response.edit_message(
            view=vista,
            attachments=[]
        )

    async def cb_cargar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CargarMensajeModal(self))

    async def cb_borrar(self, interaction: discord.Interaction):
        for bloque in self.borrador["bloques"]:
            borrar_archivos_bloque(bloque)

        BORRADORES.pop(str(self.autor_id), None)
        guardar_borradores()

        self.sel = None
        await self.refrescar(interaction)


# ---------- COMANDO /EMBED ----------

@bot.tree.command(
    name="embed",
    description="Crea una tarjeta personalizada"
)
@app_commands.describe(
    canal="Canal de texto o foro donde se publicará"
)
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.guild_only()
async def crear_embed(
    interaction: discord.Interaction,
    canal: Optional[discord.TextChannel | discord.ForumChannel] = None
):

    destino = canal or interaction.channel

    if isinstance(destino, discord.ForumChannel):

        await interaction.response.send_modal(
            TituloPublicacionModal(
                interaction.user.id,
                destino
            )
        )

    elif isinstance(destino, discord.TextChannel):

        vista = EditorV2View(
            interaction.user.id,
            destino
        )

        await interaction.response.send_message(
            view=vista,
            files=vista.files,
            ephemeral=True
        )

    else:
        await interaction.response.send_message(
            "Selecciona un canal de texto o un foro.",
            ephemeral=True
        )


# INICIAR BOT

if not TOKEN:
    print(" No se encontró la variable TOKEN.")
else:
    bot.run(TOKEN)
