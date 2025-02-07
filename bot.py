import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, Select, TextInput
import json
import asyncio
from datetime import datetime
import io
import os
from zoneinfo import ZoneInfo  # للحصول على توقيت مصر

# تحميل الإعدادات من ملف config.json
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# إعدادات البوت العامة
ADMIN_ROLE_ID = config["admin_role_id"]
GUILD_ID = config["guild_id"]
CONTROL_CHANNEL_ID = config["control_channel_id"]
LOG_CHANNEL_1_ID = config["log_channel_1_id"]
LOG_CHANNEL_2_ID = config["log_channel_2_id"]
SEND_DELAY = config["send_delay"]
UPDATE_INTERVAL = config["update_interval"]
SUPPORT_STATS_CHANNEL_ID = config["support_stats_channel_id"]
TICKET_CHANNEL_ID = config["ticket_channel_id"]

# ملفات البيانات
SUBBOTS_FILE = "sub_bots.json"
ENCRYPTED_FILE = "encrypted_words.json"
FAQ_FILE = "faq.json"
SUPPORT_STATS_FILE = "support_stats.json"
AUTO_LINE_IMAGE_FILE = "auto_line_image.json"  # لتخزين صورة الخط التلقائي
AUTO_LINE_CHANNELS_FILE = "auto_line_channels.json"  # لتخزين روم الخط التلقائي

# تحميل بيانات البوتات الفرعية
def load_sub_bots():
    try:
        with open(SUBBOTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_sub_bots(data):
    with open(SUBBOTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

sub_bots = load_sub_bots()
running_bots = {}

# تحميل الكلمات المشفرة
try:
    with open(ENCRYPTED_FILE, "r", encoding="utf-8") as file:
        encrypted_words = json.load(file)
except FileNotFoundError:
    encrypted_words = {}

# تحميل الأسئلة الشائعة
def load_faq():
    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_faq(data):
    with open(FAQ_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

faq_data = load_faq()

# تحميل إحصائيات الدعم
def load_support_stats():
    if os.path.exists(SUPPORT_STATS_FILE):
        try:
            with open(SUPPORT_STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_support_stats(data):
    with open(SUPPORT_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

support_stats = load_support_stats()

# تحميل صورة الخط التلقائي
def load_auto_line_image():
    try:
        with open(AUTO_LINE_IMAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("image_url")
    except Exception:
        return None

def save_auto_line_image(url):
    with open(AUTO_LINE_IMAGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"image_url": url}, f, indent=4, ensure_ascii=False)

# تحميل روم الخط التلقائي
def load_auto_line_channels():
    try:
        with open(AUTO_LINE_CHANNELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("channels", [])
    except Exception:
        return []

def save_auto_line_channels(channels):
    with open(AUTO_LINE_CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump({"channels": channels}, f, indent=4, ensure_ascii=False)

auto_line_channels = load_auto_line_channels()

# إعداد intents للبوت
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# ======================================================
# الجزء الخاص بالبوتات الفرعية والبث
# ======================================================
class SubBotClient:
    def __init__(self, name, token):
        self.name = name
        self.token = token
        self.client = commands.Bot(command_prefix="!", intents=intents, loop=bot.loop)
        self._setup_events()

    def _setup_events(self):
        @self.client.event
        async def on_ready():
            print(f"[SubBot] {self.name} connected as {self.client.user}!")

    async def start(self):
        try:
            await self.client.start(self.token)
        except Exception as e:
            print(f"[SubBot] Error in {self.name}: {e}")

    async def stop(self):
        await self.client.close()

# ======================================================
# لوحة التحكم للبث
# ======================================================
class ControlPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Permission denied!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕ Add Bot", style=discord.ButtonStyle.green, custom_id="add_bot")
    async def add_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddBotModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Remove Bot", style=discord.ButtonStyle.red, custom_id="remove_bot")
    async def remove_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [discord.SelectOption(label=name) for name in sub_bots.keys()]
        view = View()
        view.add_item(Select(options=options, custom_id="remove_select"))
        await interaction.response.send_message("Select bot to remove:", view=view, ephemeral=True)

    @discord.ui.button(label="📡 Start Broadcast", style=discord.ButtonStyle.primary, custom_id="start_broadcast")
    async def start_broadcast(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [discord.SelectOption(label=name) for name in sub_bots.keys()]
        view = View()
        view.add_item(Select(options=options, custom_id="broadcast_select"))
        await interaction.response.send_message("Select broadcast bot:", view=view, ephemeral=True)

class AddBotModal(Modal):
    def __init__(self):
        super().__init__(title="Add New Bot")
        self.add_item(TextInput(label="Bot Name"))
        self.add_item(TextInput(label="Bot Token"))

    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value.strip()
        token = self.children[1].value.strip()
        sub_bots[name] = token
        save_sub_bots(sub_bots)
        await start_sub_bot(name, token)
        await interaction.response.send_message(f"✅ {name} added!", ephemeral=True)

class RecipientSelect(Select):
    def __init__(self, bot_name, message):
        options = [
            discord.SelectOption(label="All Members", value="all"),
            discord.SelectOption(label="Online Members", value="online"),
            discord.SelectOption(label="Specific Member", value="specific")
        ]
        super().__init__(placeholder="Select recipients...", options=options)
        self.bot_name = bot_name
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = bot.get_guild(GUILD_ID)
        target_bot = running_bots.get(self.bot_name)
        if not target_bot:
            return await interaction.followup.send("❌ Bot not found.", ephemeral=True)
        
        if self.values[0] == "specific":
            await interaction.followup.send("Enter user ID:", ephemeral=True)
            try:
                msg = await bot.wait_for("message", check=lambda m: m.author == interaction.user, timeout=60)
                member = guild.get_member(int(msg.content))
                members = [member] if member else []
            except Exception as e:
                print(e)
                members = []
        else:
            members = [m for m in guild.members if not m.bot]
            if self.values[0] == "online":
                members = [m for m in members if m.status != discord.Status.offline]

        log_channel = bot.get_channel(LOG_CHANNEL_2_ID)
        embed = discord.Embed(title="🚀 جاري الإرسال...", color=discord.Color.orange())
        embed.add_field(name="✅ تم الإرسال", value="\nلا يوجد\n", inline=False)
        embed.add_field(name="❌ فشل الإرسال", value="\nلا يوجد\n", inline=False)
        status_message = await log_channel.send(embed=embed)

        success = []
        failed = []

        for i, member in enumerate(members, 1):
            try:
                await target_bot.client.get_user(member.id).send(self.message)
                success.append(member.mention)
                await asyncio.sleep(SEND_DELAY)
            except Exception as e:
                failed.append(f"{member.mention} - {str(e)}")

            if i % UPDATE_INTERVAL == 0 or i == len(members):
                success_display = "\n".join(success[-10:]) or "لا يوجد"
                failed_display = "\n".join(failed[-10:]) or "لا يوجد"
                embed = discord.Embed(
                    title=f"📤 جاري الإرسال ({i}/{len(members)})",
                    color=discord.Color.blue()
                )
                embed.add_field(name=f"✅ تم الإرسال ({len(success)})", value=f"\n{success_display}\n", inline=False)
                embed.add_field(name=f"❌ فشل الإرسال ({len(failed)})", value=f"\n{failed_display}\n", inline=False)
                await status_message.edit(embed=embed)

        final_embed = discord.Embed(
            title="✅ اكتمل الإرسال",
            description=f"تم إرسال {len(success)}/{len(members)} رسالة",
            color=discord.Color.green()
        )
        final_embed.add_field(name="النجاحات", value="\n".join(success[:10]) or "لا يوجد", inline=False)
        final_embed.add_field(name="الإخفاقات", value="\n".join(failed[:10]) or "لا يوجد", inline=False)
        await status_message.edit(embed=final_embed)
        
        await log_broadcast(interaction.user, self.bot_name, self.message, members, success, failed)

async def log_broadcast(user, bot_name, message, members, success, failed):
    log_channel = bot.get_channel(LOG_CHANNEL_1_ID)
    embed = discord.Embed(title="📊 تقرير البث", color=discord.Color.blue())
    embed.add_field(name="المشغل", value=user.mention)
    embed.add_field(name="البوت المستخدم", value=bot_name)
    embed.add_field(name="الرسالة", value=message[:500], inline=False)
    embed.add_field(name="النجاحات", value=str(len(success)), inline=True)
    embed.add_field(name="الإخفاقات", value=str(len(failed)), inline=True)
    await log_channel.send(embed=embed)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("❌ Permission denied!", ephemeral=True)
        return
    custom_id = interaction.data.get("custom_id")
    if custom_id == "remove_select":
        name = interaction.data["values"][0]
        del sub_bots[name]
        save_sub_bots(sub_bots)
        await stop_sub_bot(name)
        await interaction.response.send_message(f"✅ {name} deleted!", ephemeral=True)
    elif custom_id == "broadcast_select":
        bot_name = interaction.data["values"][0]
        await interaction.response.send_message("Enter message:", ephemeral=True)
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            view = View()
            view.add_item(RecipientSelect(bot_name, msg.content))
            await interaction.followup.send("Select recipients:", view=view, ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Timeout!", ephemeral=True)

async def start_sub_bot(name, token):
    if name not in running_bots:
        bot_instance = SubBotClient(name, token)
        running_bots[name] = bot_instance
        asyncio.create_task(bot_instance.start())
        print(f"[Main] Sub-bot '{name}' started.")

async def stop_sub_bot(name):
    if name in running_bots:
        await running_bots[name].stop()
        del running_bots[name]
        print(f"[Main] Sub-bot '{name}' stopped.")

# ======================================================
# أوامر البوت الرئيسي للتشفير
# ======================================================
@bot.command()
async def اضافه(ctx, *, text):
    global encrypted_words
    lines = text.split("\n")
    response = "تمت إضافة الكلمات التالية:\n"
    for line in lines:
        parts = line.split()
        if len(parts) == 2:
            word, encrypted = parts
            encrypted_words[word] = encrypted
            response += f"{word} → {encrypted}\n"
    with open(ENCRYPTED_FILE, "w", encoding="utf-8") as file:
        json.dump(encrypted_words, file, ensure_ascii=False, indent=4)
    await ctx.send(response)

@bot.command()
async def تشفير(ctx, *, message):
    encrypted_message = message
    for word, encrypted in encrypted_words.items():
        encrypted_message = encrypted_message.replace(word, encrypted)
    await ctx.send(encrypted_message)

@bot.command()
async def قائمه(ctx):
    if not encrypted_words:
        await ctx.send("📜 القائمة فارغة، لم يتم إضافة أي كلمات بعد!")
        return
    response = "📜 قائمة الكلمات المشفرة:\n"
    for word, encrypted in encrypted_words.items():
        response += f"{word} → {encrypted}\n"
    await ctx.send(response)

# ======================================================
# نظام الأسئلة الشائعة (FAQ)
# ======================================================
@bot.command(name="اضافه_سوأل")
async def add_faq(ctx):
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("من فضلك ادخل السؤال:")
    try:
        question_msg = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        return await ctx.send("انتهى الوقت. حاول مرة أخرى.")
    
    await ctx.send("الآن ادخل الإجابة:")
    try:
        answer_msg = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        return await ctx.send("انتهى الوقت. حاول مرة أخرى.")
    
    question = question_msg.content.strip()
    answer = answer_msg.content.strip()
    faq_data[question] = answer
    save_faq(faq_data)
    await ctx.send("✅ تم إضافة السؤال والإجابة بنجاح!")

class FAQSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=q) for q in faq_data.keys()]
        if not options:
            options = [discord.SelectOption(label="لا توجد أسئلة شائعة", value="none", default=True)]
        super().__init__(placeholder="اختر سؤالاً شائعاً...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("لا توجد أسئلة متوفرة حالياً.", ephemeral=True)
        question = self.values[0]
        answer = faq_data.get(question, "لا توجد إجابة مسجلة.")
        await interaction.response.send_message(f"**السؤال:** {question}\n**الجواب:** {answer}", ephemeral=True)

class FAQView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FAQSelect())

# ======================================================
# نظام التذاكر
# ======================================================
class TicketModal(Modal, title="فتح تذكرة"):
    ticket_reason = TextInput(
        label="سبب فتح التذكرة", 
        style=discord.TextStyle.long,
        placeholder="اكتب سبب فتح التذكرة بالتفصيل...",
        required=True,
        max_length=500
    )
    def __init__(self, ticket_type: str):
        super().__init__()
        self.ticket_type = ticket_type

    async def on_submit(self, interaction: discord.Interaction):
        ticket_type = self.ticket_type
        ticket_reason = self.ticket_reason.value
        guild = interaction.guild
        author = interaction.user
        try:
            cat_config = config["ticket_categories"][ticket_type]
        except KeyError:
            return await interaction.response.send_message("نوع التذكرة غير معروف.", ephemeral=True)
        category_id = cat_config["category_id"]
        support_role_id = cat_config["role_id"]
        support_role = guild.get_role(support_role_id)
        if support_role is None:
            return await interaction.response.send_message("❌ الدور المحدد للدعم غير موجود في السيرفر.", ephemeral=True)
        # إعداد الأذونات بدون تضمين المنشن داخل الإيمبد
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        channel_name = f"ticket-{author.name}-{int(datetime.utcnow().timestamp())}"
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=discord.Object(id=category_id),
            overwrites=overwrites,
            reason=f"تذكرة من {author} - نوع: {ticket_type}"
        )
        # إرسال رسالة منشن خاصة بفريق الدعم (خارج رسالة الإيمبد)
        await ticket_channel.send(content=support_role.mention)
        # إرسال رسالة إيمبد بدون منشن
        embed = discord.Embed(
            title="تم فتح التذكرة",
            description=f"**سبب التذكرة:** {ticket_reason}\n**العميل:** {author.mention} ({author.id})",
            color=0x00AE86,
            timestamp=datetime.utcnow()
        )
        # تمرير ticket_type إلى view الإجراءات
        view = TicketActionView(ticket_channel, author, support_role_id, ticket_type)
        await ticket_channel.send(embed=embed, view=view)
        
        # إرسال رسالة قائمة الأسئلة الشائعة إن وجدت
        if faq_data:
            faq_embed = discord.Embed(
                title="❓ الأسئلة الشائعة",
                description="يمكنك اختيار سؤال من القائمة أدناه لمعرفة الإجابة.",
                color=0x5865F2
            )
            await ticket_channel.send(embed=faq_embed, view=FAQView())
        
        await interaction.response.send_message(f"تم إنشاء تذكرتك: {ticket_channel.mention}", ephemeral=True)

class TicketActionView(View):
    def __init__(self, ticket_channel: discord.TextChannel, ticket_creator: discord.Member, support_role_id: int, ticket_type: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.ticket_channel = ticket_channel
        self.ticket_creator = ticket_creator
        self.support_role_id = support_role_id
        self.ticket_type = ticket_type
        self.claimed_by = None  # العضو الذي استلم التذكرة

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_role_ids = [role.id for role in interaction.user.roles]
        if self.support_role_id not in user_role_ids:
            await interaction.response.send_message("❌ انت لست من فريق الدعم.", ephemeral=True)
            return
        if self.claimed_by is None:
            self.claimed_by = interaction.user
        await self.ticket_channel.send(f"تم استلام التذكرة من قبل {interaction.user.mention} ({interaction.user.id}). سيتم مساعدتك قريبًا.")
        await interaction.response.send_message("لقد استلمت التذكرة.", ephemeral=True)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        close_embed = discord.Embed(
            title="تم إغلاق التذكرة",
            description="اضغط على زر حذف التذكرة لتسجيلها وحذف القناة.",
            color=0x808080,
            timestamp=datetime.utcnow()
        )
        view = DeleteTicketView(self.ticket_channel, self.ticket_creator, self.claimed_by, self.ticket_type)
        await self.ticket_channel.send(embed=close_embed, view=view)
        await interaction.response.send_message("تم إغلاق التذكرة. اضغط على زر حذف التذكرة عند الانتهاء.", ephemeral=True)
        self.disable_all_items()
        await self.ticket_channel.edit(view=self)

class DeleteTicketView(View):
    def __init__(self, ticket_channel: discord.TextChannel, ticket_creator: discord.Member, claimed_by: discord.Member, ticket_type: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.ticket_channel = ticket_channel
        self.ticket_creator = ticket_creator
        self.claimed_by = claimed_by  # عضو الدعم الذي استلم التذكرة
        self.ticket_type = ticket_type
        self.transcript_saved = False  # علم للتأكد من حفظ التذكرة

    @discord.ui.button(label="حذف التذكرة", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.transcript_saved:
            # حفظ التذكرة (Transcript) وعدم حذف القناة فوراً
            messages = [message async for message in self.ticket_channel.history(limit=200)]
            messages.sort(key=lambda m: m.created_at)
            
            claim_info = "غير محدد"
            participants = set()
            for msg in messages:
                participants.add(msg.author.display_name)
                if "تم استلام التذكرة من قبل" in msg.content:
                    claim_info = msg.content.strip()
            participants_list = ", ".join(participants)
            
            message_entries = ""
            for msg in messages:
                timestamp = msg.created_at.strftime("%H:%M")
                username = msg.author.display_name
                avatar_url = msg.author.avatar.url if msg.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
                content = msg.content.strip()
                if not content:
                    if msg.embeds:
                        embed_texts = []
                        for embed in msg.embeds:
                            if embed.title:
                                embed_texts.append(f"عنوان: {embed.title}")
                            if embed.description:
                                embed_texts.append(f"الوصف: {embed.description}")
                        content = "\n".join(embed_texts)
                    if not content and msg.attachments:
                        content = "\n".join([attachment.url for attachment in msg.attachments])
                if not content:
                    content = "[لا يوجد نص]"
                content = content.replace("<", "&lt;").replace(">", "&gt;")
                message_entries += f"""
                <div class="message">
                    <div class="avatar">
                        <img src="{avatar_url}" alt="avatar">
                    </div>
                    <div class="bubble">
                        <div class="header">
                            <span class="username">{username}</span>
                            <span class="timestamp">{timestamp}</span>
                        </div>
                        <div class="content">{content}</div>
                    </div>
                </div>
                """
            
            info_section = f"""
            <div class="ticket-header">
                <h2>تفاصيل التذكرة</h2>
                <p><strong>اسم التذكرة:</strong> {self.ticket_channel.name}</p>
                <p><strong>العميل (الذي فتح التذكرة):</strong> {self.ticket_creator.mention}</p>
                <p><strong>المستلم (فريق الدعم):</strong> {claim_info}</p>
                <p><strong>المشاركون:</strong> {participants_list}</p>
                <p><strong>عدد الرسائل:</strong> {len(messages)}</p>
                <p><strong>تاريخ الإنشاء:</strong> {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
                <p><strong>فئة التذكرة:</strong> {self.ticket_type}</p>
            </div>
            """
            
            html_template = f"""
            <!DOCTYPE html>
            <html lang="ar">
            <head>
                <meta charset="UTF-8">
                <title>Transcript - {self.ticket_channel.name}</title>
                <style>
                    body {{
                        background-color: #36393f;
                        font-family: "Whitney", "Helvetica Neue", Helvetica, Arial, sans-serif;
                        color: #dcddde;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{
                        max-width: 800px;
                        margin: auto;
                        background-color: #2f3136;
                        border-radius: 8px;
                        box-shadow: 0 0 10px rgba(0,0,0,0.5);
                        overflow: hidden;
                    }}
                    .ticket-header {{
                        background-color: #202225;
                        padding: 20px;
                        border-bottom: 1px solid #72767d;
                    }}
                    .ticket-header h2 {{
                        margin: 0 0 10px 0;
                        font-size: 1.5em;
                        color: #fff;
                    }}
                    .ticket-header p {{
                        margin: 5px 0;
                        font-size: 0.9em;
                    }}
                    .chat-container {{
                        padding: 20px;
                        background-color: #36393f;
                    }}
                    .message {{
                        display: flex;
                        margin-bottom: 15px;
                    }}
                    .avatar {{
                        flex-shrink: 0;
                        margin-right: 10px;
                    }}
                    .avatar img {{
                        width: 40px;
                        height: 40px;
                        border-radius: 50%;
                    }}
                    .bubble {{
                        background-color: #40444b;
                        padding: 10px 15px;
                        border-radius: 8px;
                        position: relative;
                        max-width: 80%;
                    }}
                    .bubble::after {{
                        content: "";
                        position: absolute;
                        top: 10px;
                        left: -8px;
                        border-width: 8px;
                        border-style: solid;
                        border-color: transparent #40444b transparent transparent;
                    }}
                    .header {{
                        display: flex;
                        align-items: center;
                        margin-bottom: 5px;
                    }}
                    .username {{
                        font-weight: bold;
                        margin-right: 10px;
                        color: #fff;
                    }}
                    .timestamp {{
                        font-size: 0.8em;
                        color: #72767d;
                    }}
                    .content {{
                        white-space: pre-wrap;
                        line-height: 1.4;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    {info_section}
                    <div class="chat-container">
                        {message_entries}
                    </div>
                </div>
            </body>
            </html>
            """
            html_bytes = html_template.encode("utf-8")
            file_for_log = discord.File(io.BytesIO(html_bytes), filename=f"{self.ticket_channel.name}_transcript.html")
            
            info_embed = discord.Embed(title="📄 تقرير التذكرة", color=discord.Color.blurple())
            info_embed.add_field(name="اسم التذكرة", value=self.ticket_channel.name, inline=True)
            info_embed.add_field(name="العميل", value=self.ticket_creator.mention, inline=True)
            info_embed.add_field(name="المستلم", value=claim_info, inline=True)
            info_embed.add_field(name="المشاركون", value=participants_list if participants_list else "غير محدد", inline=False)
            info_embed.add_field(name="عدد الرسائل", value=str(len(messages)), inline=True)
            info_embed.add_field(name="تاريخ الإنشاء", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
            info_embed.add_field(name="فئة التذكرة", value=self.ticket_type, inline=True)
            
            log_channel = self.ticket_channel.guild.get_channel(config["log_channel_id"])
            log_message = None
            if log_channel:
                log_message = await log_channel.send(embed=info_embed, file=file_for_log)
            
            # إرسال التقرير إلى العميل عبر الخاص
            try:
                file_for_dm = discord.File(io.BytesIO(html_bytes), filename=f"{self.ticket_channel.name}_transcript.html")
                await self.ticket_creator.send(embed=info_embed, file=file_for_dm)
            except Exception as e:
                print(f"تعذر إرسال الخاص للعميل: {e}")
            
            # تحديث إحصائيات الدعم: حفظ التفاصيل في شكل dict
            if self.claimed_by is not None and log_message is not None:
                sid = str(self.claimed_by.id)
                egypt_time = datetime.now(ZoneInfo("Africa/Cairo")).strftime("%Y-%m-%d %H:%M:%S")
                # تحديد فئة التذكرة اعتماداً على الدور (يمكنك التعديل حسب الحاجة)
                support_role = self.ticket_channel.guild.get_role(self.support_role_id)
                support_category = support_role.name if support_role else "غير محدد"
                if sid not in support_stats:
                    support_stats[sid] = {
                        "tickets_accepted": 0,
                        "ticket_logs": [],  # قائمة من dict لكل تذكرة
                        "stats_message_id": None,
                        "support_category": support_category
                    }
                support_stats[sid]["tickets_accepted"] += 1
                support_stats[sid]["ticket_logs"].append({
                    "link": log_message.jump_url,
                    "close_date": egypt_time,
                    "ticket_type": self.ticket_type
                })
                save_support_stats(support_stats)
                stats_channel = self.ticket_channel.guild.get_channel(SUPPORT_STATS_CHANNEL_ID)
                if stats_channel is not None:
                    try:
                        stats_msg = None
                        if support_stats[sid]["stats_message_id"]:
                            try:
                                stats_msg = await stats_channel.fetch_message(support_stats[sid]["stats_message_id"])
                            except Exception:
                                stats_msg = None
                        content = f"**إحصائيات {self.claimed_by.mention}:**\n"
                        content += f"عدد التذاكر المستلمة: {support_stats[sid]['tickets_accepted']}\n"
                        content += "التذاكر:\n"
                        for log in support_stats[sid]["ticket_logs"]:
                            content += f"- {log['link']} | {log['close_date']} | فئة: {log['ticket_type']}\n"
                        content += f"\nفئة الدعم: {support_stats[sid]['support_category']}"
                        if stats_msg:
                            await stats_msg.edit(content=content)
                        else:
                            new_msg = await stats_channel.send(content=content)
                            support_stats[sid]["stats_message_id"] = new_msg.id
                            save_support_stats(support_stats)
                    except Exception as e:
                        print(f"Error updating support stats message: {e}")
            
            await interaction.response.send_message("تم تسجيل التذكرة. اضغط مرة أخرى لحذفها.", ephemeral=True)
            self.transcript_saved = True
        else:
            await interaction.response.send_message("تم حفظ التذكرة سابقاً. جاري حذف التذكرة...", ephemeral=True)
            await self.ticket_channel.delete(reason="حذف التذكرة بعد تسجيلها.")

# عرض أزرار فتح التذكرة
class TicketButtonsView(View):
    def __init__(self, timeout: float = None):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="فتح تذكرة دعم", style=discord.ButtonStyle.primary, custom_id="open_ticket_support")
    async def open_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketModal(ticket_type="support")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="فتح تذكرة شراء", style=discord.ButtonStyle.success, custom_id="open_ticket_purchase")
    async def open_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketModal(ticket_type="purchase")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="فتح تذكرة تصليح", style=discord.ButtonStyle.danger, custom_id="open_ticket_repair")
    async def open_repair(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketModal(ticket_type="repair")
        await interaction.response.send_modal(modal)

# ======================================================
# أوامر الإدارة: Ban, Unban, Kick, مسح
# ======================================================
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member = None, *, reason=None):
    if member is None:
        return await ctx.send("يرجى تحديد العضو المراد حظره.")
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ تم حظر {member.mention}")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {e}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, member_id: int = None):
    if member_id is None:
        return await ctx.send("يرجى إدخال ID العضو.")
    banned = await ctx.guild.bans()
    for ban_entry in banned:
        user = ban_entry.user
        if user.id == member_id:
            try:
                await ctx.guild.unban(user)
                return await ctx.send(f"✅ تم فك الحظر عن {user.mention}")
            except Exception as e:
                return await ctx.send(f"❌ حدث خطأ: {e}")
    await ctx.send("العضو ليس محظور.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member = None, *, reason=None):
    if member is None:
        await ctx.send("يرجى إدخال ID العضو:")
        try:
            msg = await bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=30)
            member = ctx.guild.get_member(int(msg.content))
            if member is None:
                return await ctx.send("لم يتم العثور على العضو.")
        except asyncio.TimeoutError:
            return await ctx.send("انتهى الوقت.")
    try:
        try:
            await member.send(f"لقد تم طردك من السيرفر.\nالسبب: {reason if reason else 'لم يتم تحديد سبب'}")
        except:
            pass
        await member.kick(reason=reason)
        await ctx.send(f"✅ تم طرد {member.mention}")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {e}")

@bot.command(name="مسح")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, count: int = None):
    if count is None:
        deleted = await ctx.channel.purge(limit=100)
        await ctx.send(f"✅ تم مسح {len(deleted)} رسالة.", delete_after=5)
    else:
        deleted = await ctx.channel.purge(limit=count+1)
        await ctx.send(f"✅ تم مسح {len(deleted)-1} رسالة.", delete_after=5)

# ======================================================
# نظام الخط التلقائي
# ======================================================
@bot.command()
async def خط(ctx):
    # عند كتابة الامر "خط" في الشات يتم إرسال صورة الخط المحفوظة
    image_url = load_auto_line_image()
    if image_url:
        msg = await ctx.send(image_url)
        await ctx.message.delete()
    else:
        await ctx.send("لم يتم تعيين صورة للخط. يرجى إرسال صورة مع الأمر لتعيينها.")

@bot.command()
async def تعيين_صورة_الخط(ctx):
    if ctx.message.attachments:
        image = ctx.message.attachments[0]
        await image.save(fp="line_image.png")
        # يمكنك رفع الصورة إلى مكان ثابت أو استخدام رابط الصورة إذا كان البوت يدعم ذلك
        # هنا نقوم بحفظ رابط افتراضي بعد رفعه (يجب عليك تعديل هذه الجزئية بحسب آلية رفع الصور)
        image_url = f"https://your.cdn.com/line_image.png"
        save_auto_line_image(image_url)
        await ctx.send("✅ تم تعيين صورة الخط.")
    else:
        await ctx.send("يرجى إرفاق صورة مع الأمر.")

@bot.command()
async def إضافة_روم_الخط(ctx, channel: discord.TextChannel):
    if channel.id not in auto_line_channels:
        auto_line_channels.append(channel.id)
        save_auto_line_channels(auto_line_channels)
        await ctx.send(f"✅ تم إضافة {channel.mention} لنظام الخط التلقائي.")
    else:
        await ctx.send("هذا الروم موجود بالفعل في النظام.")

@bot.command()
async def إزالة_روم_الخط(ctx, channel: discord.TextChannel):
    if channel.id in auto_line_channels:
        auto_line_channels.remove(channel.id)
        save_auto_line_channels(auto_line_channels)
        await ctx.send(f"✅ تم إزالة {channel.mention} من نظام الخط التلقائي.")
    else:
        await ctx.send("هذا الروم غير موجود في النظام.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # إذا كانت الرسالة في روم الخط التلقائي، يتم إرسال صورة الخط
    if message.channel.id in auto_line_channels and message.content != "":
        image_url = load_auto_line_image()
        if image_url:
            await message.channel.send(image_url)
            try:
                await message.delete()
            except:
                pass
    await bot.process_commands(message)

# ======================================================
# نظام الرتب
# ======================================================
class RankView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(RankSelect())

class RankSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="إنشاء رتبة", value="create"),
            discord.SelectOption(label="حذف رتبة", value="delete"),
            discord.SelectOption(label="رتب العضو", value="member")
        ]
        super().__init__(placeholder="اختر العملية...", options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "create":
            await interaction.response.send_message("يرجى كتابة اسم الرتبة الجديدة:", ephemeral=True)
            try:
                msg = await bot.wait_for("message", check=lambda m: m.author == interaction.user, timeout=30)
                role_name = msg.content.strip()
                # يمكنك إضافة خيارات صلاحيات ومكان الرتبة هنا حسب الحاجة
                new_role = await interaction.guild.create_role(name=role_name)
                await interaction.followup.send(f"✅ تم إنشاء الرتبة {new_role.name}", ephemeral=True)
            except asyncio.TimeoutError:
                await interaction.followup.send("انتهى الوقت.", ephemeral=True)
        elif choice == "delete":
            roles = [role for role in interaction.guild.roles if role.name != "@everyone"]
            options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
            select = Select(placeholder="اختر الرتبة للحذف", options=options)
            async def role_delete_callback(i: discord.Interaction):
                role_id = int(select.values[0])
                role = interaction.guild.get_role(role_id)
                if role:
                    await role.delete(reason="حذف بواسطة نظام الرتب")
                    await i.response.send_message(f"✅ تم حذف الرتبة {role.name}", ephemeral=True)
                else:
                    await i.response.send_message("❌ الرتبة غير موجودة.", ephemeral=True)
            select.callback = role_delete_callback
            view = View()
            view.add_item(select)
            await interaction.response.send_message("اختر الرتبة التي تريد حذفها:", view=view, ephemeral=True)
        elif choice == "member":
            options = [
                discord.SelectOption(label="إضافة رتبة للعضو", value="add"),
                discord.SelectOption(label="إزالة رتبة من العضو", value="remove")
            ]
            select = Select(placeholder="اختر العملية", options=options)
            async def member_role_callback(i: discord.Interaction):
                if select.values[0] == "add":
                    await i.response.send_message("يرجى ذكر العضو الذي تريد إضافة رتبة له:", ephemeral=True)
                    try:
                        msg = await bot.wait_for("message", check=lambda m: m.author == i.user, timeout=30)
                        member = msg.mentions[0] if msg.mentions else None
                        if not member:
                            return await i.followup.send("❌ لم يتم العثور على العضو.", ephemeral=True)
                        # عرض قائمة بالرتب التي لا يمتلكها العضو
                        available_roles = [role for role in i.guild.roles if role not in member.roles and role.name != "@everyone"]
                        if not available_roles:
                            return await i.followup.send("لا توجد رتب متاحة للإضافة.", ephemeral=True)
                        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in available_roles]
                        select_role = Select(placeholder="اختر الرتبة", options=options)
                        async def add_role_callback(ii: discord.Interaction):
                            role_id = int(select_role.values[0])
                            role = i.guild.get_role(role_id)
                            if role:
                                await member.add_roles(role)
                                await ii.response.send_message(f"✅ تمت إضافة {role.name} لـ {member.mention}", ephemeral=True)
                            else:
                                await ii.response.send_message("❌ الرتبة غير موجودة.", ephemeral=True)
                        select_role.callback = add_role_callback
                        view = View()
                        view.add_item(select_role)
                        await i.followup.send("اختر الرتبة لإضافتها:", view=view, ephemeral=True)
                    except asyncio.TimeoutError:
                        await i.followup.send("انتهى الوقت.", ephemeral=True)
                elif select.values[0] == "remove":
                    await i.response.send_message("يرجى ذكر العضو الذي تريد إزالة رتبة منه:", ephemeral=True)
                    try:
                        msg = await bot.wait_for("message", check=lambda m: m.author == i.user, timeout=30)
                        member = msg.mentions[0] if msg.mentions else None
                        if not member:
                            return await i.followup.send("❌ لم يتم العثور على العضو.", ephemeral=True)
                        member_roles = [role for role in member.roles if role.name != "@everyone"]
                        if not member_roles:
                            return await i.followup.send("لا يمتلك العضو رتباً.", ephemeral=True)
                        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in member_roles]
                        select_role = Select(placeholder="اختر الرتبة", options=options)
                        async def remove_role_callback(ii: discord.Interaction):
                            role_id = int(select_role.values[0])
                            role = i.guild.get_role(role_id)
                            if role:
                                await member.remove_roles(role)
                                await ii.response.send_message(f"✅ تمت إزالة {role.name} من {member.mention}", ephemeral=True)
                            else:
                                await ii.response.send_message("❌ الرتبة غير موجودة.", ephemeral=True)
                        select_role.callback = remove_role_callback
                        view = View()
                        view.add_item(select_role)
                        await i.followup.send("اختر الرتبة لإزالتها:", view=view, ephemeral=True)
                    except asyncio.TimeoutError:
                        await i.followup.send("انتهى الوقت.", ephemeral=True)
            select.callback = member_role_callback
            await interaction.response.send_message("اختر العملية التي تريد تنفيذها على رتب العضو:", view=View().add_item(select), ephemeral=True)

@bot.command()
async def رتبه(ctx):
    await ctx.send("اختر العملية المطلوبة:", view=RankView())

# ======================================================
# أمر المساعدة
# ======================================================
@bot.command()
async def help(ctx):
    help_text = """
**قائمة الأوامر:**
+ban @member [reason] - حظر عضو من السيرفر.
+unban member_id - فك حظر عضو.
+kick @member [reason] - طرد عضو من السيرفر.
+مسح [عدد] - مسح الرسائل من الشات.
+خط - إرسال صورة الخط التلقائي.
+تعيين_صورة_الخط - تعيين صورة الخط (يجب إرفاق صورة مع الأمر).
+إضافة_روم_الخط #channel - إضافة روم لنظام الخط التلقائي.
+إزالة_روم_الخط #channel - إزالة روم من نظام الخط التلقائي.
+رتبه - إدارة الرتب (إنشاء، حذف، إضافة/إزالة رتب للعضو).
+اضافه - لإضافة كلمات التشفير.
+تشفير - لتشفير الرسائل.
+قائمه - عرض قائمة الكلمات المشفرة.
+اضافه_سوأل - إضافة سؤال شائع.
    """
    await ctx.send(help_text)

# ======================================================
# on_ready الموحد للبوت وإعداد الرسائل الأساسية
# ======================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await setup_control_panel()
    for name, token in sub_bots.items():
        await start_sub_bot(name, token)
    guild = bot.get_guild(config["guild_id"])
    if guild is None:
        print("لم يتم العثور على السيرفر باستخدام المعرف المحدد في التكوين.")
    else:
        ticket_channel = guild.get_channel(TICKET_CHANNEL_ID)
        if ticket_channel is None:
            print("لم يتم العثور على القناة الخاصة بالتذاكر.")
        else:
            message_found = None
            async for msg in ticket_channel.history(limit=50):
                if msg.author == bot.user and msg.embeds and msg.embeds[0].title == "📞 دعم فني":
                    message_found = msg
                    break
            support_embed = discord.Embed(
                title="📞 دعم فني",
                description="للحصول على دعم فني اضغط الزر أدناه لفتح تذكرة.",
                color=0x00AE86
            )
            view = TicketButtonsView(timeout=None)
            if message_found:
                await message_found.edit(embed=support_embed, view=view)
                print("تم تحديث رسالة التذاكر القائمة.")
            else:
                await ticket_channel.send(embed=support_embed, view=view)
                print("تم إرسال رسالة التذاكر الجديدة.")
    print("البوت جاهز.")

async def setup_control_panel():
    channel = bot.get_channel(CONTROL_CHANNEL_ID)
    if channel is None:
        print("❌ لم يتم العثور على قناة التحكم. تأكد من صحة CONTROL_CHANNEL_ID في config.json.")
        return
    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()
    embed = discord.Embed(title="🎛️ لوحة التحكم", color=discord.Color.gold())
    await channel.send(embed=embed, view=ControlPanel())

# ======================================================
# تشغيل البوت
# ======================================================
bot.run(config["token"])
