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
CANAL_ASCENSOS_ID = 1554335232617095179    # Canal donde se publican ascensos y descensos. 0 = el mismo canal donde se usa el comando

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
import uuid

# RECLUTAMIENTO CON FORMULARIO
# CONFIGURACION DEL RECLUTAMIENTO -------------------------------------------------------------------------------------

CANAL_RECLUTAMIENTO_ID = 1554330185736650802
CANAL_SOLICITUDES_RECLUTAMIENTO_ID = 1568144369511440515
CANAL_LOGS_RECLUTAMIENTO_ID = 1568144615830196274
CANAL_IMAGENES_RECLUTAMIENTO_ID = 1554330185736650802
ROL_PING_RECLUTAMIENTO_ID = 1568142087948345405
ROL_ENLISTAMIENTO_ID = 1554362466564186142
ROLES_EXTRA_RECLUTAMIENTO_IDS = [1554367563440328734, 1554368070145937469]

URL_REQUISITOS = ""
URL_MXRP_COMANDOS = "https://discord.com/channels/1193021133981765632/1247772158722310214"

# Relleno invisible para que el embed de la solicitud salga ancho
RELLENO_ANCHO = "\u2800" * 60
TIEMPO_FORMULARIO = 1800

# Tipos: "texto", "imagen", "select"
PREGUNTAS = [
    {"tipo": "texto", "texto": "¿Cómo llegaste a Grupo Televisa?, si fue invitado adjunta el nombre de la persona."},
    {"tipo": "texto", "texto": "¿Cuál es tu experiencia en MXRP u otros servidores de roleplay?"},
    {"tipo": "imagen", "texto": "Coloca una foto de tu INE / PASAPORTE de MXRP (obligatorio, si no lo tienes tramítalo en MXRP)."},
    {"tipo": "texto", "texto": "Inserta tu Usuario de Roblox."},
    {"tipo": "texto", "texto": "De el 1 al 10, ¿Qué tan buena redacción tiene?."},
    {"tipo": "select", "texto": "Respetaré a mis compañeros y seguiré las órdenes de los directivos."},
    {"tipo": "select", "texto": "Prometo tener compromiso y actividad constante en Grupo Televisa."},
]


class SesionReclutamiento:
    """Estado del formulario de un usuario (se guarda en memoria mientras lo contesta)."""

    def __init__(self, miembro: discord.Member):
        self.user = miembro
        self.respuestas = {}
        self.ocupada = False
        self.paso = 0
        self.iniciado = False
        self.inicio = datetime.now(timezone.utc)
        self.mensaje: Optional[discord.Message] = None


SESIONES: dict = {}


def embed_rec(texto: str, pregunta: Optional[int] = None) -> discord.Embed:
    descripcion = texto
    if pregunta is not None:
        descripcion += f"\n\n**Pregunta: {pregunta}/{len(PREGUNTAS)}.**"

    embed = discord.Embed(
        title=f"Reclutamiento de {NOMBRE}.",
        description=descripcion,
        color=COLOR_TELEVISA
    )
    embed.set_footer(
        text=NOMBRE,
        icon_url=bot.user.display_avatar.url if bot.user else None
    )
    return embed


async def quitar_botones(mensaje: Optional[discord.Message]):
    if mensaje is None:
        return
    try:
        await mensaje.edit(view=None)
    except Exception:
        pass


async def cancelar_formulario(interaction: discord.Interaction, sesion: SesionReclutamiento):
    SESIONES.pop(sesion.user.id, None)
    await interaction.response.edit_message(
        embed=embed_rec(
            "Cancelaste el formulario. Si quieres volver a intentarlo, elige la opción de nuevo en el canal de reclutamiento."
        ),
        view=None
    )


class VistaSesion(discord.ui.View):
    """Base de los mensajes del formulario: si el usuario no responde, la sesión expira."""

    def __init__(self, sesion: SesionReclutamiento):
        super().__init__(timeout=TIEMPO_FORMULARIO)
        self.sesion = sesion

    async def on_timeout(self):
        s = self.sesion
        mensaje = getattr(self, "message", None)

        if SESIONES.get(s.user.id) is s and mensaje and s.mensaje and s.mensaje.id == mensaje.id:
            SESIONES.pop(s.user.id, None)
            try:
                await mensaje.edit(
                    embed=embed_rec(
                        "Tu formulario expiró por inactividad. Vuelve a elegir la opción en el canal de reclutamiento."
                    ),
                    view=None
                )
            except Exception:
                pass


class IniciarView(VistaSesion):

    @discord.ui.button(label="Iniciar Formulario", style=discord.ButtonStyle.success)
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.sesion.iniciado = True
        self.sesion.paso = 0
        self.sesion.inicio = datetime.now(timezone.utc)

        await interaction.response.edit_message(view=None)
        self.stop()
        await enviar_pregunta(self.sesion)

    @discord.ui.button(label="Cancelar Formulario", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await cancelar_formulario(interaction, self.sesion)
        self.stop()


class PreguntaView(VistaSesion):
    """Preguntas de texto o imagen: solo tienen el botón de cancelar."""

    @discord.ui.button(label="Cancelar Formulario", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await cancelar_formulario(interaction, self.sesion)
        self.stop()


class PreguntaSelectView(VistaSesion):
    """Preguntas de Si / No: menú desplegable + botón de cancelar."""

    @discord.ui.select(
        placeholder="Seleccionar opción",
        options=[
            discord.SelectOption(label="Si", value="Si"),
            discord.SelectOption(label="No", value="No"),
        ],
    )
    async def seleccion(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.sesion.respuestas[self.sesion.paso] = select.values[0]
        self.stop()
        await avanzar_formulario(self.sesion)

    @discord.ui.button(label="Cancelar Formulario", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await cancelar_formulario(interaction, self.sesion)
        self.stop()


async def enviar_pregunta(sesion: SesionReclutamiento):
    pregunta = PREGUNTAS[sesion.paso]
    embed = embed_rec(f"**{pregunta['texto']}**", sesion.paso + 1)

    vista = PreguntaSelectView(sesion) if pregunta["tipo"] == "select" else PreguntaView(sesion)

    try:
        sesion.mensaje = await sesion.user.send(embed=embed, view=vista)
    except Exception as e:
        print(f" No pude enviar la pregunta del formulario a {sesion.user}: {e}")
        SESIONES.pop(sesion.user.id, None)


async def avanzar_formulario(sesion: SesionReclutamiento):
    await quitar_botones(sesion.mensaje)
    sesion.paso += 1

    if sesion.paso >= len(PREGUNTAS):
        await finalizar_formulario(sesion)
    else:
        await enviar_pregunta(sesion)


@bot.listen("on_message")
async def respuestas_formulario(message: discord.Message):
    """Recibe las respuestas de texto e imagen que el usuario manda por DM."""

    if message.author.bot or message.guild is not None:
        return

    sesion = SESIONES.get(message.author.id)

    if sesion is None or not sesion.iniciado or sesion.ocupada:
        return

    pregunta = PREGUNTAS[sesion.paso]

    if pregunta["tipo"] == "select":
        return await message.channel.send("Para esta pregunta usa el menú desplegable de arriba.")

    if pregunta["tipo"] == "texto":
        texto = message.content.strip()

        if not texto:
            return await message.channel.send("Responde esta pregunta escribiendo un mensaje.")

        if len(texto) > 900:
            return await message.channel.send("Tu respuesta es muy larga (máximo 900 caracteres).")

        valor = texto

    else:
        imagenes = [a for a in message.attachments if es_imagen(a)]

        if not imagenes:
            return await message.channel.send("Debes adjuntar una imagen como respuesta a esta pregunta.")

        valor = imagenes[0]

    sesion.ocupada = True

    try:
        sesion.respuestas[sesion.paso] = valor
        await avanzar_formulario(sesion)
    finally:
        sesion.ocupada = False


async def finalizar_formulario(sesion: SesionReclutamiento):
    SESIONES.pop(sesion.user.id, None)

    usuario = sesion.user
    canal = bot.get_channel(CANAL_SOLICITUDES_RECLUTAMIENTO_ID) if CANAL_SOLICITUDES_RECLUTAMIENTO_ID else None

    if not canal:
        print(" No encontré el canal de solicitudes de reclutamiento (revisa CANAL_SOLICITUDES_RECLUTAMIENTO_ID).")
        await usuario.send(embed=embed_rec("No pude enviar tu solicitud. Avisa a un directivo."))
        return

    duracion = int((datetime.now(timezone.utc) - sesion.inicio).total_seconds())
    ahora = int(datetime.now(timezone.utc).timestamp())
    fecha = datetime.now(ZONA_HORARIA).strftime("%d/%m/%Y")
    r = sesion.respuestas

    # Orden de las respuestas:
    # r[0] cómo llegó | r[1] experiencia | r[2] foto INE | r[3] usuario de Roblox
    # r[4] foto de sus servidores de discord | r[5] respeto | r[6] compromiso

    unido = getattr(sesion.user, "joined_at", None)
    unido_txt = f"<t:{int(unido.timestamp())}:R>" if unido else "Desconocido"
    creada_txt = f"<t:{int(usuario.created_at.timestamp())}:R>"

    try:
        canal_imagenes = (
            bot.get_channel(CANAL_IMAGENES_RECLUTAMIENTO_ID)
            if CANAL_IMAGENES_RECLUTAMIENTO_ID else None
        ) or canal

        ine = await r[2].to_file(filename=f"ine_{usuario.id}{extension_archivo(r[2])}")
        servidores = await r[4].to_file(filename=f"servidores_{usuario.id}{extension_archivo(r[4])}")

        msg_imagenes = await canal_imagenes.send(
            content=f"Pruebas de la solicitud de {usuario.name} (`{usuario.id}`)",
            files=[ine, servidores],
            allowed_mentions=discord.AllowedMentions.none()
        )

        link_ine = msg_imagenes.attachments[0].url
        link_servidores = msg_imagenes.attachments[1].url

        embed = discord.Embed(
            description=(
                f"# SOLICITUD DE RECLUTAMIENTO\n"
                f"**Solicitante:** {usuario.mention}\n"
                f"### 1. ¿Cómo llegaste a {NOMBRE}?\n{r[0]}\n"
                f"### 2. Experiencia en MXRP / roleplay.\n{r[1]}\n"
                f"### 3. Foto de tu INE / PASAPORTE de MXRP.\n[Imagen adjunta (1)]({link_ine})\n"
                f"### 4. Usuario de Roblox.\n{r[3]}\n"
                f"### 5. Foto de todos tus servidores de discord.\n[Imagen adjunta (2)]({link_servidores})\n"
                f"### 6. Respetaré a mis compañeros y seguiré las órdenes de los directivos.\n{r[5]}\n"
                f"### 7. Prometo tener compromiso y actividad constante.\n{r[6]}\n"
                f"**Estadísticas de la solicitud**\n"
                f"ID de usuario: `{usuario.id}`\n"
                f"Nombre de usuario: `{usuario.name}`\n"
                f"Usuario: {usuario.mention}\n"
                f"Duración: `{duracion}s`\n"
                f"Cuenta creada: {creada_txt}\n"
                f"Se unió al servidor: {unido_txt}\n"
                f"Enviada: <t:{ahora}:R>\n"
                f"ID de solicitud: `{uuid.uuid4().hex[:20]}`\n"
                f"{RELLENO_ANCHO}"
            )[:4096],
            color=COLOR_TELEVISA,
        )

        embed.add_field(name="Estado:", value="Pendiente", inline=True)
        embed.add_field(name="Fecha:", value=fecha, inline=True)
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.set_footer(
            text=f"{NOMBRE} • Solicitud {usuario.id}",
            icon_url=canal.guild.icon.url if canal.guild.icon else None
        )

        if ROL_PING_RECLUTAMIENTO_ID:
            permitidos = discord.AllowedMentions(
                roles=[discord.Object(id=ROL_PING_RECLUTAMIENTO_ID)],
                users=False
            )
            contenido = f"<@&{ROL_PING_RECLUTAMIENTO_ID}>"
        else:
            permitidos = discord.AllowedMentions.none()
            contenido = None

        await canal.send(
            content=contenido,
            embed=embed,
            view=SolicitudReclutamientoView(),
            allowed_mentions=permitidos,
        )

    except Exception as e:
        print(f" Error enviando la solicitud de reclutamiento: {e!r}")
        try:
            await usuario.send(embed=embed_rec("No pude enviar tu solicitud. Avisa a un directivo."))
        except Exception:
            pass
        return

    try:
        await usuario.send(embed=embed_rec(
            "**Formulario enviado.**\nTu solicitud fue enviada correctamente. "
            "Un directivo la revisará y te avisaremos por este chat."
        ))
    except Exception:
        pass


# ---------- Panel con el menú "Televisa | Formulario" ----------

class PanelReclutamientoView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="panel_reclutamiento",
        placeholder="Haz una selección",
        options=[
            discord.SelectOption(label="Televisa | Formulario", value="televisa_formulario"),
        ],
    )
    async def seleccion(self, interaction: discord.Interaction, select: discord.ui.Select):

        await interaction.response.defer(ephemeral=True)

        # Reinicia el menú para que no se quede la opción marcada
        try:
            await interaction.message.edit(view=PanelReclutamientoView())
        except Exception:
            pass

        usuario = interaction.user

        if isinstance(usuario, discord.Member) and obtener_rango_actual(usuario) >= 0:
            return await interaction.followup.send(f"Ya eres miembro de {NOMBRE}.", ephemeral=True)

        if usuario.id in SESIONES:
            return await interaction.followup.send(
                "Ya tienes un formulario en curso. Revisa tus mensajes privados.", ephemeral=True
            )

        sesion = SesionReclutamiento(usuario)
        SESIONES[usuario.id] = sesion

        embed = embed_rec(f"Vas a iniciar el formulario para pertenecer a {NOMBRE}.")

        try:
            sesion.mensaje = await usuario.send(embed=embed, view=IniciarView(sesion))
        except discord.Forbidden:
            SESIONES.pop(usuario.id, None)
            return await interaction.followup.send(
                "No puedo enviarte mensajes privados. Activa tus **mensajes directos** en la configuración de privacidad "
                "del servidor y vuelve a intentarlo.",
                ephemeral=True
            )
        except Exception as e:
            SESIONES.pop(usuario.id, None)
            print(f" Error enviando el formulario por DM a {usuario}: {e}")
            return await interaction.followup.send("No pude enviarte el formulario. Intenta de nuevo.", ephemeral=True)

        await interaction.followup.send("Te envié el formulario por mensaje privado.", ephemeral=True)


@bot.tree.command(name="panel-reclutamiento", description="Publica el panel de reclutamiento con el formulario")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def panel_reclutamiento(interaction: discord.Interaction):

    canal = bot.get_channel(CANAL_RECLUTAMIENTO_ID) if CANAL_RECLUTAMIENTO_ID else interaction.channel

    if not canal:
        return await interaction.response.send_message("No encontré el canal de reclutamiento.", ephemeral=True)

    ruta_fondo = buscar_archivo("fondo.png")

    if ruta_fondo is None:
        return await interaction.response.send_message(
            "Falta **fondo.png** junto a bot.py. Súbelo en la misma carpeta.", ephemeral=True
        )

    lineas = [
        f"# Reclutamiento de {NOMBRE}.",
        f"***Completa el siguiente formulario para convertirte en trabajador de {NOMBRE}.***",
        "",
    ]
    if URL_REQUISITOS:
        lineas.append(f"> **Revisa los requisitos en {URL_REQUISITOS} antes de iniciar tu reclutamiento.**\n")
    lineas.append("> **Tu INE / PASAPORTE es obligatorio, si no lo tienes tramítalo en MXRP**.\n")
    lineas.append(f"> **En {URL_MXRP_COMANDOS} utiliza /tramitar ine o pasaporte.**")

    embed = discord.Embed(description="\n".join(lineas), color=COLOR_TELEVISA)
    embed.set_image(url="attachment://fondo.png")
    embed.set_footer(text=NOMBRE, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    try:
        await canal.send(
            embed=embed,
            view=PanelReclutamientoView(),
            file=discord.File(ruta_fondo, filename="fondo.png"),
        )
    except Exception as e:
        print(f" Error publicando el panel de reclutamiento: {e!r}")
        return await interaction.response.send_message(
            f"No pude publicar el panel. Error: `{type(e).__name__}: {e}`", ephemeral=True
        )

    await interaction.response.send_message("Panel de reclutamiento publicado correctamente.", ephemeral=True)


# ---------- Solicitud en el canal de solicitudes: Aceptar / Rechazar ----------

def id_solicitante_reclutamiento(embed: discord.Embed) -> Optional[int]:
    """Lee el ID del solicitante desde el pie del embed (así los botones sirven aunque el bot se reinicie)."""
    texto = embed.footer.text if embed.footer and embed.footer.text else ""
    coincidencia = re.search(r"Solicitud (\d+)", texto)
    return int(coincidencia.group(1)) if coincidencia else None


async def avisar_por_dm(usuario_id: int, embed: discord.Embed) -> bool:
    try:
        usuario = await bot.fetch_user(usuario_id)
        await usuario.send(embed=embed)
        return True
    except Exception as e:
        print(f" No pude enviar el DM a {usuario_id}: {e}")
        return False


async def mensaje_actualizado(interaction: discord.Interaction, mensaje: discord.Message) -> discord.Message:
    """Vuelve a leer el mensaje para saber si otro directivo ya resolvió la solicitud."""
    try:
        return await interaction.channel.fetch_message(mensaje.id)
    except Exception:
        return mensaje


def ya_resuelta(mensaje: discord.Message) -> bool:
    embed = mensaje.embeds[0] if mensaje.embeds else None
    return bool(embed and embed.fields and embed.fields[0].value != "Pendiente")


async def dar_roles_reclutamiento(guild: discord.Guild, usuario: discord.Member, responsable):
    """Da los roles iniciales y quita el rol de aspirante. Devuelve (roles, retirados, None) o (None, [], error)."""

    ids_roles = [SEPARADORES_RANGO[0], JERARQUIA[0]] + list(ROLES_EXTRA_RECLUTAMIENTO_IDS)
    roles = [guild.get_role(rol_id) for rol_id in ids_roles]

    if any(rol is None for rol in roles):
        faltantes = [str(rol_id) for rol_id, rol in zip(ids_roles, roles) if rol is None]
        return None, [], "No encontré estos roles en el servidor: " + ", ".join(faltantes)

    muy_altos = [rol.name for rol in roles if rol >= guild.me.top_role]
    if muy_altos:
        return None, [], (
            "No puedo asignar estos roles porque están por encima o igual a mi rol más alto: " + ", ".join(muy_altos)
        )

    try:
        await usuario.add_roles(*roles, reason=f"Reclutado por {responsable}")
    except discord.Forbidden:
        return None, [], "No pude asignar los roles. Revisa que el bot tenga el permiso **Gestionar roles**."
    except Exception as e:
        print(f" Error reclutando a {usuario}: {e}")
        return None, [], "No pude reclutar al usuario. Revisa la consola del bot."

    retirados = []
    rol_enlistamiento = guild.get_role(ROL_ENLISTAMIENTO_ID) if ROL_ENLISTAMIENTO_ID else None
    if rol_enlistamiento is not None and rol_enlistamiento in usuario.roles:
        try:
            await usuario.remove_roles(rol_enlistamiento, reason=f"Reclutado por {responsable}")
            retirados.append(rol_enlistamiento)
        except Exception as e:
            print(f" No pude quitar el rol de aspirante a {usuario}: {e}")

    return roles, retirados, None


async def enviar_log_reclutamiento(usuario: discord.Member, responsable, roles: list, retirados: list):
    if not CANAL_LOGS_RECLUTAMIENTO_ID:
        return
    canal_log = bot.get_channel(CANAL_LOGS_RECLUTAMIENTO_ID)
    if not canal_log:
        print(" No encontré el canal de logs de reclutamiento.")
        return

    lista_roles = "\n".join(f"- {rol.name}" for rol in roles)
    retirados_txt = ""
    if retirados:
        retirados_txt = "**Roles retirados:**\n" + "\n".join(f"- {r.name}" for r in retirados) + "\n\n"

    embed_log = discord.Embed(
        description=(
            f"# RECLUTAMIENTO\n\n"
            f"{usuario.mention} ya fue **reclutado**.\n\n"
            f"**Responsable:**\n{responsable.mention}\n\n"
            f"**Roles otorgados:**\n{lista_roles}\n\n"
            f"{retirados_txt}"
            f"**ID de usuario:**\n{usuario.id}\n\n"
            f"**Nombre de Discord:**\n{usuario.name}\n\n"
            f"**Fecha:**\n{datetime.now(ZONA_HORARIA).strftime('%d/%m/%Y')}"
        ),
        color=COLOR_TELEVISA,
    )
    embed_log.set_footer(text=NOMBRE, icon_url=usuario.guild.icon.url if usuario.guild.icon else None)
    try:
        await canal_log.send(embed=embed_log, allowed_mentions=discord.AllowedMentions.none())
    except Exception as e:
        print(f" Error enviando log de reclutamiento: {e}")


class AceptarReclutaModal(ModalBase, title="Aceptar solicitud"):

    motivo = discord.ui.Label(
        text="Motivo (opcional)",
        description="Si lo escribes, el usuario lo recibirá por mensaje privado.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Mensaje de bienvenida, observaciones...",
            max_length=500,
            required=False,
        ),
    )

    def __init__(self, mensaje: discord.Message, solicitante_id: int):
        super().__init__()
        self.mensaje = mensaje
        self.solicitante_id = solicitante_id

    async def on_submit(self, interaction: discord.Interaction):

        motivo = (self.motivo.component.value or "").strip()
        guild = interaction.guild

        await interaction.response.defer(ephemeral=True)

        mensaje = await mensaje_actualizado(interaction, self.mensaje)

        if ya_resuelta(mensaje):
            return await interaction.followup.send("Esta solicitud ya fue resuelta.", ephemeral=True)

        try:
            miembro = guild.get_member(self.solicitante_id) or await guild.fetch_member(self.solicitante_id)
        except discord.NotFound:
            return await interaction.followup.send(
                "El usuario ya no está en el servidor. Puedes rechazar la solicitud.", ephemeral=True
            )

        roles, retirados, error = await dar_roles_reclutamiento(guild, miembro, interaction.user)

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await enviar_log_reclutamiento(miembro, interaction.user, roles, retirados)

        # Actualiza la solicitud: estado Aceptado y se quitan los botones
        try:
            embeds = [e.copy() for e in mensaje.embeds]
            extra = f"\n\n**Aceptado por:** {interaction.user.mention}"
            if motivo:
                extra += f"\n**Motivo:** {motivo}"
            embeds[0].description = ((embeds[0].description or "") + extra)[:4096]
            embeds[0].color = discord.Color.from_rgb(120, 177, 89)
            embeds[0].set_field_at(0, name="Estado:", value="Aceptado", inline=True)
            await mensaje.edit(embeds=embeds, view=None)
        except Exception as e:
            print(f" Error actualizando la solicitud de reclutamiento: {e}")

        # DM al solicitante
        texto_dm = f"**¡Felicidades!** Tu solicitud de reclutamiento a {NOMBRE} fue **aceptada**."
        if motivo:
            texto_dm += f"\n\n**Motivo:**\n{motivo}"
        dm_ok = await avisar_por_dm(self.solicitante_id, embed_rec(texto_dm))

        if dm_ok:
            await interaction.followup.send("Solicitud aceptada: roles otorgados y usuario avisado por DM.", ephemeral=True)
        else:
            await interaction.followup.send(
                "Solicitud aceptada y roles otorgados, pero no pude enviar el DM (tiene los mensajes privados cerrados).",
                ephemeral=True
            )


class RechazarReclutaModal(ModalBase, title="Rechazar solicitud"):

    motivo = discord.ui.Label(
        text="Motivo (opcional)",
        description="Si lo escribes, el usuario lo recibirá por mensaje privado.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Explica por qué se rechaza la solicitud...",
            max_length=500,
            required=False,
        ),
    )

    def __init__(self, mensaje: discord.Message, solicitante_id: int):
        super().__init__()
        self.mensaje = mensaje
        self.solicitante_id = solicitante_id

    async def on_submit(self, interaction: discord.Interaction):

        motivo = (self.motivo.component.value or "").strip()

        await interaction.response.defer(ephemeral=True)

        mensaje = await mensaje_actualizado(interaction, self.mensaje)

        if ya_resuelta(mensaje):
            return await interaction.followup.send("Esta solicitud ya fue resuelta.", ephemeral=True)

        # Actualiza la solicitud: estado Rechazado y se quitan los botones
        try:
            embeds = [e.copy() for e in mensaje.embeds]
            extra = f"\n\n**Rechazado por:** {interaction.user.mention}"
            if motivo:
                extra += f"\n**Motivo:** {motivo}"
            embeds[0].description = ((embeds[0].description or "") + extra)[:4096]
            embeds[0].color = discord.Color.from_rgb(221, 46, 68)
            embeds[0].set_field_at(0, name="Estado:", value="Rechazado", inline=True)
            await mensaje.edit(embeds=embeds, view=None)
        except Exception as e:
            print(f" Error actualizando la solicitud de reclutamiento: {e}")

        # DM al solicitante (sin decir quién la rechazó)
        texto_dm = "Tu solicitud de reclutamiento fue **rechazada**."
        if motivo:
            texto_dm += f"\n\n**Motivo:**\n{motivo}"
        dm_ok = await avisar_por_dm(self.solicitante_id, embed_rec(texto_dm))

        if dm_ok:
            await interaction.followup.send("Solicitud rechazada y usuario avisado por DM.", ephemeral=True)
        else:
            await interaction.followup.send(
                "Solicitud rechazada, pero no pude enviar el DM (tiene los mensajes privados cerrados).",
                ephemeral=True
            )


class SolicitudReclutamientoView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def _validar(self, interaction: discord.Interaction) -> Optional[int]:
        """Revisa permiso y estado. Devuelve el ID del solicitante o None si ya respondió con un error."""
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("No tienes permiso para usar estos botones.", ephemeral=True)
            return None

        if not interaction.message.embeds:
            await interaction.response.send_message("No pude leer los datos de esta solicitud.", ephemeral=True)
            return None

        solicitante_id = id_solicitante_reclutamiento(interaction.message.embeds[0])

        if solicitante_id is None:
            await interaction.response.send_message("No pude leer los datos de esta solicitud.", ephemeral=True)
            return None

        if ya_resuelta(interaction.message):
            await interaction.response.send_message("Esta solicitud ya fue resuelta.", ephemeral=True)
            return None

        return solicitante_id

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.success, custom_id="reclutamiento_aceptar")
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        solicitante_id = await self._validar(interaction)
        if solicitante_id is None:
            return
        await interaction.response.send_modal(AceptarReclutaModal(interaction.message, solicitante_id))

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger, custom_id="reclutamiento_rechazar")
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        solicitante_id = await self._validar(interaction)
        if solicitante_id is None:
            return
        await interaction.response.send_modal(RechazarReclutaModal(interaction.message, solicitante_id))


_INICIO_RECLUTAMIENTO = {"hecho": False}


@bot.listen("on_ready")
async def reclutamiento_al_iniciar():
    """Recupera los botones del panel y de las solicitudes después de reiniciar el bot."""
    if _INICIO_RECLUTAMIENTO["hecho"]:
        return
    _INICIO_RECLUTAMIENTO["hecho"] = True
    bot.add_view(PanelReclutamientoView())
    bot.add_view(SolicitudReclutamientoView())

# INICIAR BOT

if not TOKEN:
    print(" No se encontró la variable TOKEN.")
else:
    bot.run(TOKEN)
