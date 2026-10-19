"""Built-in categories and well-known services (with bundled logos) for vault entries."""

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logos")


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    color: str
    symbol: str


@dataclass(frozen=True)
class Brand:
    key: str
    name: str
    category: str
    domain: str

    @property
    def url(self) -> str:
        return f"https://{self.domain}"

    @property
    def logo_path(self) -> Optional[str]:
        path = os.path.join(LOGO_DIR, f"{self.key}.png")
        return path if os.path.exists(path) else None


CATEGORIES = [
    Category("banks", "Banks", "#22c55e", "\U0001F3E6"),
    Category("wallets", "Digital Wallets", "#f59e0b", "\U0001F4B3"),
    Category("streaming", "Streaming", "#ef4444", "\U0001F3AC"),
    Category("music", "Music", "#a855f7", "\U0001F3B5"),
    Category("email", "Email", "#3b82f6", "\u2709\ufe0f"),
    Category("social", "Social Media", "#ec4899", "\U0001F4AC"),
    Category("developer", "Developer", "#64748b", "\U0001F4BB"),
    Category("shopping", "Shopping & Rides", "#f97316", "\U0001F6CD\ufe0f"),
    Category("gaming", "Gaming", "#06b6d4", "\U0001F3AE"),
    Category("work", "Work & Cloud", "#b45309", "\U0001F4BC"),
    Category("other", "Other", "#8b8fa8", "\U0001F5C2\ufe0f"),
]
ALL_SYMBOL = "\U0001F511"
CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}
DEFAULT_CATEGORY = "other"

_B = Brand
BRANDS = [
    # Pakistani banks
    _B("hbl", "HBL", "banks", "hbl.com"),
    _B("ubl", "UBL", "banks", "ubldigital.com"),
    _B("mcb", "MCB Bank", "banks", "mcb.com.pk"),
    _B("alfalah", "Bank Alfalah", "banks", "bankalfalah.com"),
    _B("meezan", "Meezan Bank", "banks", "meezanbank.com"),
    _B("abl", "Allied Bank", "banks", "abl.com"),
    _B("nbp", "National Bank of Pakistan", "banks", "nbp.com.pk"),
    _B("bahl", "Bank AL Habib", "banks", "bankalhabib.com"),
    _B("faysal", "Faysal Bank", "banks", "faysalbank.com"),
    _B("askari", "Askari Bank", "banks", "askaribank.com"),
    _B("habibmetro", "HabibMetro", "banks", "habibmetro.com"),
    _B("jsbank", "JS Bank", "banks", "jsbl.com"),
    _B("bop", "The Bank of Punjab", "banks", "bop.com.pk"),
    _B("bankislami", "BankIslami", "banks", "bankislami.com.pk"),
    _B("soneri", "Soneri Bank", "banks", "soneribank.com"),
    _B("scb", "Standard Chartered", "banks", "sc.com"),
    _B("dib", "Dubai Islamic Bank", "banks", "dibpak.com"),
    # Digital wallets & payments
    _B("jazzcash", "JazzCash", "wallets", "jazzcash.com.pk"),
    _B("easypaisa", "Easypaisa", "wallets", "easypaisa.com.pk"),
    _B("sadapay", "SadaPay", "wallets", "sadapay.pk"),
    _B("nayapay", "NayaPay", "wallets", "nayapay.com"),
    _B("upaisa", "UPaisa", "wallets", "upaisa.com"),
    _B("paypal", "PayPal", "wallets", "paypal.com"),
    _B("payoneer", "Payoneer", "wallets", "payoneer.com"),
    _B("wise", "Wise", "wallets", "wise.com"),
    _B("binance", "Binance", "wallets", "binance.com"),
    _B("skrill", "Skrill", "wallets", "skrill.com"),
    # Streaming
    _B("netflix", "Netflix", "streaming", "netflix.com"),
    _B("youtube", "YouTube", "streaming", "youtube.com"),
    _B("primevideo", "Prime Video", "streaming", "primevideo.com"),
    _B("disneyplus", "Disney+", "streaming", "disneyplus.com"),
    _B("hbomax", "HBO Max", "streaming", "max.com"),
    _B("tamasha", "Tamasha", "streaming", "tamashaweb.com"),
    _B("tapmad", "Tapmad", "streaming", "tapmad.com"),
    _B("shahid", "Shahid", "streaming", "shahid.mbc.net"),
    _B("twitch", "Twitch", "streaming", "twitch.tv"),
    # Music
    _B("spotify", "Spotify", "music", "spotify.com"),
    _B("applemusic", "Apple Music", "music", "music.apple.com"),
    _B("youtubemusic", "YouTube Music", "music", "music.youtube.com"),
    _B("soundcloud", "SoundCloud", "music", "soundcloud.com"),
    _B("deezer", "Deezer", "music", "deezer.com"),
    _B("anghami", "Anghami", "music", "anghami.com"),
    _B("amazonmusic", "Amazon Music", "music", "music.amazon.com"),
    # Email
    _B("gmail", "Gmail", "email", "mail.google.com"),
    _B("outlook", "Outlook", "email", "outlook.com"),
    _B("yahoo", "Yahoo Mail", "email", "mail.yahoo.com"),
    _B("protonmail", "Proton Mail", "email", "proton.me"),
    _B("icloud", "iCloud Mail", "email", "icloud.com"),
    # Social media
    _B("facebook", "Facebook", "social", "facebook.com"),
    _B("instagram", "Instagram", "social", "instagram.com"),
    _B("x", "X (Twitter)", "social", "x.com"),
    _B("linkedin", "LinkedIn", "social", "linkedin.com"),
    _B("tiktok", "TikTok", "social", "tiktok.com"),
    _B("snapchat", "Snapchat", "social", "snapchat.com"),
    _B("whatsapp", "WhatsApp", "social", "whatsapp.com"),
    _B("reddit", "Reddit", "social", "reddit.com"),
    _B("discord", "Discord", "social", "discord.com"),
    _B("telegram", "Telegram", "social", "telegram.org"),
    # Developer
    _B("github", "GitHub", "developer", "github.com"),
    _B("gitlab", "GitLab", "developer", "gitlab.com"),
    _B("bitbucket", "Bitbucket", "developer", "bitbucket.org"),
    _B("stackoverflow", "Stack Overflow", "developer", "stackoverflow.com"),
    _B("aws", "AWS", "developer", "aws.amazon.com"),
    _B("azure", "Microsoft Azure", "developer", "azure.microsoft.com"),
    _B("gcloud", "Google Cloud", "developer", "cloud.google.com"),
    _B("vercel", "Vercel", "developer", "vercel.com"),
    _B("digitalocean", "DigitalOcean", "developer", "digitalocean.com"),
    _B("docker", "Docker Hub", "developer", "hub.docker.com"),
    # Shopping, food & rides
    _B("daraz", "Daraz", "shopping", "daraz.pk"),
    _B("amazon", "Amazon", "shopping", "amazon.com"),
    _B("aliexpress", "AliExpress", "shopping", "aliexpress.com"),
    _B("ebay", "eBay", "shopping", "ebay.com"),
    _B("olx", "OLX", "shopping", "olx.com.pk"),
    _B("foodpanda", "foodpanda", "shopping", "foodpanda.pk"),
    _B("careem", "Careem", "shopping", "careem.com"),
    _B("uber", "Uber", "shopping", "uber.com"),
    _B("indrive", "inDrive", "shopping", "indrive.com"),
    # Gaming
    _B("steam", "Steam", "gaming", "store.steampowered.com"),
    _B("epicgames", "Epic Games", "gaming", "epicgames.com"),
    _B("playstation", "PlayStation", "gaming", "playstation.com"),
    _B("xbox", "Xbox", "gaming", "xbox.com"),
    _B("riot", "Riot Games", "gaming", "riotgames.com"),
    _B("pubg", "PUBG", "gaming", "pubg.com"),
    # Work & cloud
    _B("microsoft", "Microsoft 365", "work", "microsoft.com"),
    _B("googledrive", "Google Drive", "work", "drive.google.com"),
    _B("dropbox", "Dropbox", "work", "dropbox.com"),
    _B("slack", "Slack", "work", "slack.com"),
    _B("zoom", "Zoom", "work", "zoom.us"),
    _B("notion", "Notion", "work", "notion.so"),
    _B("canva", "Canva", "work", "canva.com"),
    _B("chatgpt", "ChatGPT", "work", "chatgpt.com"),
    _B("fiverr", "Fiverr", "work", "fiverr.com"),
    _B("upwork", "Upwork", "work", "upwork.com"),
]
BRAND_BY_KEY = {b.key: b for b in BRANDS}


def brands_in(category: str) -> list[Brand]:
    return [b for b in BRANDS if b.category == category]


def _host(text: str) -> str:
    text = text.strip().lower()
    if not text:
        return ""
    netloc = urlparse(text if "://" in text else f"https://{text}").netloc
    netloc = netloc.split("@")[-1].split(":")[0]
    return netloc[4:] if netloc.startswith("www.") else netloc


def detect_brand(website: str, title: str = "") -> Optional[Brand]:
    """Best-effort match of a free-typed website or title to a known service."""
    host = _host(website) if " " not in website.strip() else ""
    if host:
        # Longest domain first, so music.youtube.com wins over youtube.com.
        for b in sorted(BRANDS, key=lambda b: -len(b.domain)):
            if host == b.domain or host.endswith("." + b.domain):
                return b
    for text in (title, website):
        name = text.strip().lower()
        if name:
            for b in BRANDS:
                if name == b.name.lower() or name == b.key:
                    return b
    return None


def resolve_brand(brand_key: str, website: str, title: str) -> Optional[Brand]:
    return BRAND_BY_KEY.get(brand_key) or detect_brand(website, title)
