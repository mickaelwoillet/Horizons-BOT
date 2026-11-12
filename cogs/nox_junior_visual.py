"""NOX Junior V0.8: deterministic, original offline illustrations.

Pure renderer: no Discord or SQLite dependency, suitable for a future mobile API.
"""
from __future__ import annotations
import io
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

PALETTE = {'bleu':(63,155,242),'violet':(164,111,228),'rose':(242,137,192),
           'rouge':(226,94,115),'orange':(244,165,91),'vert':(106,199,142),
           'turquoise':(72,210,202),'dore':(232,193,91), 'arc_en_ciel':(178,130,231)}
STAGES = ('oeuf','nouveau_ne','bebe','adolescent','adulte')
MOODS = ('endormi','besoin','heureux','calme')
THEMES = ('cosmos','foret','nuages','cristaux','sanctuaire_etoiles','palais_nuages','jardin_lucioles','palais_celeste','observatoire_lunaire','jardin_cristallin')
RAINBOW = ((228,60,78),(246,143,55),(246,210,70),(80,188,112),(62,151,230),(139,92,203))
THEME_COLORS = {'cosmos':((16,22,51),(31,41,84)), 'foret':((17,52,57),(43,96,76)),
                'nuages':((61,91,145),(151,181,211)), 'cristaux':((36,28,75),(84,69,132))}

def _mix(c, other, t):
    return tuple(round(a*(1-t)+b*t) for a,b in zip(c,other))

def render(pet, stage='bebe', mood='calme', theme='cosmos', decoration='none', size=(760,440)):
    """Return PNG bytes; no user text or arbitrary paths are ever rendered."""
    if stage not in STAGES or mood not in MOODS or theme not in THEMES:
        raise ValueError('Invalid visual state')
    color = str(pet.get('color','bleu'))
    if color not in PALETTE: raise ValueError('Unknown color')
    w,h = size
    if w < 240 or h < 180 or w > 1600 or h > 1200: raise ValueError('Invalid canvas size')
    seed = int(pet.get('id',0))
    rng = random.Random(seed)
    bg, floor = THEME_COLORS.get(theme, THEME_COLORS["cosmos"])
    im=Image.new('RGB',(w,h),bg)
    d=ImageDraw.Draw(im)
    def xy(*v): return tuple(round(v[i]*(w if i%2==0 else h)/760 if i%2==0 else v[i]*h/440) for i in range(len(v)))
    def oval(box, **kw): d.ellipse(xy(*box),**kw)
    def line(points,**kw): d.line([xy(*p) for p in points],**kw)
    for i in range(110):
        x,y=rng.randrange(w),rng.randrange(int(h*.76))
        if theme=='foret':
            if i%4==0: d.ellipse((x,y,x+5,y+5),fill=(98,185,129))
        elif theme=='nuages':
            if i%9==0: d.ellipse((x,y,x+60,y+17),fill=(191,210,227))
        else:
            r=rng.choice((1,1,2,3));d.ellipse((x-r,y-r,x+r,y+r),fill=(103,139,204))
    d.rectangle(xy(0,350,760,440),fill=floor)
    if theme=='cristaux':
        for x in (60,120,620,690):
            d.polygon([xy(x,345),xy(x+20,275),xy(x+48,345)],fill=(111,125,209))
    if theme=='foret':
        for x in (60,680):
            d.rectangle(xy(x-10,150,x+10,360),fill=(79,74,69))
            oval((x-75,105,x+75,230),fill=(40,117,83))
    base=PALETTE[color]
    dark=_mix(base,(30,28,67),.22)
    light=_mix(base,(255,255,255),.24)
    oval((178,347,582,403),fill=_mix(floor,(0,0,0),.25))
    if stage=='oeuf':
        oval((281,135,479,364),fill=light)
        oval((295,146,466,354),fill=base)
        if color == 'arc_en_ciel':
            mask=Image.new('L',(w,h)); md=ImageDraw.Draw(mask)
            md.ellipse(xy(295,146,466,354),fill=255)
            bands=Image.new('RGB',(w,h)); bd=ImageDraw.Draw(bands)
            for i,shade in enumerate(RAINBOW):
                y1=round(h*(146+(208*i/6))/440)
                y2=round(h*(146+(208*(i+1)/6))/440)
                bd.rectangle((0,y1,w,y2+1),fill=shade)
            im.paste(bands,(0,0),mask)
        d.polygon([xy(298,268),xy(325,251),xy(347,272),xy(371,250),xy(395,273),xy(426,251),xy(465,271)],fill=light)
        oval((332,205,344,217),fill=(40,42,79));oval((415,205,427,217),fill=(40,42,79))
    else:
        scales={'nouveau_ne':.72,'bebe':.85,'adolescent':1.02,'adulte':1.13}
        scale=scales[stage]
        cx,cy=380,244
        def tr(box):
            x1,y1,x2,y2=box
            return (cx+(x1-cx)*scale,cy+(y1-cy)*scale,cx+(x2-cx)*scale,cy+(y2-cy)*scale)
        oval(tr((230,145,322,255)),fill=dark)
        oval(tr((438,145,530,255)),fill=dark)
        oval(tr((255,106,505,359)),fill=dark)
        oval(tr((268,112,492,351)),fill=base)
        if color == 'arc_en_ciel':
            # Rainbow bands clipped to the body; facial features remain on top.
            mask=Image.new('L',(w,h)); md=ImageDraw.Draw(mask)
            md.ellipse(xy(*tr((268,112,492,351))),fill=255)
            bands=Image.new('RGB',(w,h)); bd=ImageDraw.Draw(bands)
            left,top,right,bottom=tr((268,112,492,351))
            for i,shade in enumerate(RAINBOW):
                y1=round(h*(top+(bottom-top)*i/6)/440)
                y2=round(h*(top+(bottom-top)*(i+1)/6)/440)
                bd.rectangle((0,y1,w,y2+1),fill=shade)
            im.paste(bands,(0,0),mask)
        oval(tr((296,172,367,248)),fill=(247,251,255))
        oval(tr((393,172,464,248)),fill=(247,251,255))
        if mood=='endormi':
            line([(306,211),(332,219),(358,211)],fill=(30,34,72),width=5)
            line([(402,211),(428,219),(454,211)],fill=(30,34,72),width=5)
        else:
            oval(tr((322,189,356,242)),fill=(25,34,70))
            oval(tr((404,189,438,242)),fill=(25,34,70))
            oval(tr((329,193,339,206)),fill=(255,255,255))
            oval(tr((411,193,421,206)),fill=(255,255,255))
        oval(tr((313,263,335,277)),fill=(255,185,196))
        oval(tr((425,263,447,277)),fill=(255,185,196))
        if mood=='heureux':
            d.arc(xy(*tr((350,253,409,303))),0,180,fill=(49,43,81),width=5)
        elif mood=='besoin':
            d.arc(xy(*tr((366,279,393,299))),180,360,fill=(49,43,81),width=4)
            oval(tr((452,250,462,272)),fill=(117,214,255))
        else:
            d.arc(xy(*tr((363,260,397,288))),0,180,fill=(49,43,81),width=4)
        oval(tr((335,326,378,361)),fill=dark)
        oval(tr((385,326,428,361)),fill=dark)
        if stage in ('adolescent','adulte'):
            d.polygon([xy(*p) for p in ((371,112),(381,83),(392,112))],fill=(253,223,130))
        if stage=='adulte':
            oval(tr((255,289,283,321)),fill=light)
            oval(tr((477,289,505,321)),fill=light)
    if decoration and decoration!='none':
        # Decorative display marker, without executing or opening item names.
        oval((60,345,146,366),fill=(54,63,112))
        d.polygon([xy(*p) for p in ((90,345),(103,296),(120,345))],fill=(255,217,131))
    out=io.BytesIO();im.save(out,format='PNG');out.seek(0)
    return out




def _asset_image(path):
    """Prefer optimized WebP, retain compatibility with existing PNG assets."""
    path=Path(path)
    webp=path.with_suffix('.webp')
    return webp if webp.is_file() else path


def _character_asset(root, stage, color, mood):
    """Find the exact approved illustration. No wrong-color or random fallback."""
    root=Path(root)
    if stage=='oeuf':
        return _asset_image(root/'eggs'/f'{color}.webp')
    # The baby collection uses 'neutre', not 'calme'.
    if stage=='bebe':
        aliases={'calme':'neutre','besoin':'triste'}
        chosen=aliases.get(mood,mood)
        variants=(chosen,'neutre','heureux')
    elif stage=='nouveau_ne':
        aliases={'calme':'heureux','neutre':'heureux','triste':'besoin',
                 'surpris':'heureux','amoureux':'heureux'}
        chosen=aliases.get(mood,mood)
        variants=(chosen,'heureux')
    else:
        variants=(mood,'neutre','heureux')
    for emotion in dict.fromkeys(variants):
        file=_asset_image(root/'characters'/stage/f'{stage}_{color}_{emotion}.webp')
        if file.is_file(): return file
    return root/'characters'/stage/f'__missing_{stage}_{color}.png'

def compose_room(pet, stage='bebe', mood='calme', theme=None, decorations=(), size=(1280,720)):
    """Composite PNG assets at runtime; missing assets use legacy renderer until approved files arrive."""
    from PIL import Image
    root=Path(__file__).resolve().parent.parent/'data'/'nox_junior'
    # The default 'cosmos' room has no file. Previously this returned the old
    # procedural mascot, silently ignoring every approved character illustration.
    base=_asset_image(root/'rooms'/f'{theme}.webp') if theme else None
    if stage=='oeuf':
        egg=_asset_image(root/'eggs'/f"{pet.get('color','bleu')}.webp")
        if egg.is_file():
            with Image.open(egg) as egg_img:
                result=io.BytesIO()
                egg_img.convert('RGB').resize(size,Image.Resampling.LANCZOS).save(result,format='PNG')
                result.seek(0)
                return result
    character=_character_asset(root,stage,str(pet.get('color','bleu')),mood)
    if character.is_file():
        with Image.open(character) as source:
            # Baby illustrations already include their own complete galactic
            # backgrounds: display them without shrinking into a small rectangle.
            if source.mode != 'RGBA' or source.getextrema()[3][0] == 255:
                result=io.BytesIO()
                source.convert('RGB').resize(size,Image.Resampling.LANCZOS).save(result,format='PNG')
                result.seek(0)
                return result
    if base is not None and base.is_file():
        canvas=Image.open(base).convert('RGBA').resize(size,Image.Resampling.LANCZOS)
    else:
        # Built-in cosmos backdrop for transparent newborn character cutouts.
        from PIL import ImageDraw
        canvas=Image.new('RGBA',size,(12,19,48,255))
        draw=ImageDraw.Draw(canvas)
        rng=random.Random(5107)
        for _ in range(165):
            x=rng.randrange(size[0]); y=rng.randrange(int(size[1]*.84))
            r=rng.choice((1,1,1,2,2,3))
            draw.ellipse((x-r,y-r,x+r,y+r),fill=(110,150,218,235))
        draw.ellipse((int(size[0]*.22),int(size[1]*.83),int(size[0]*.78),int(size[1]*.93)),fill=(30,42,85,255))
    # Chaque emplacement est indépendant ; couchage sous le personnage.
    from . import nox_junior_engine as economy
    slot_items = decorations.items() if isinstance(decorations,dict) else ((economy.DECOR_SLOTS.get(code),code) for code in decorations)
    for slot,code in slot_items:
        if slot not in economy.SLOT_POSITIONS or code not in economy.DECOR_SLOTS or economy.DECOR_SLOTS[code]!=slot: continue
        asset=_asset_image(root/'decorations'/f'{code}.webp')
        if not asset.is_file(): continue
        layer=Image.open(asset).convert('RGBA')
        if slot=='couchage': max_w,max_h=.36,.19
        elif slot=='sol_centre': max_w,max_h=.45,.18
        else: max_w,max_h=.17,.24
        layer.thumbnail((int(size[0]*max_w),int(size[1]*max_h)),Image.Resampling.LANCZOS)
        x,y=economy.SLOT_POSITIONS[slot]
        canvas.alpha_composite(layer,(max(0,min(size[0]-layer.width,int(x*size[0]-layer.width/2))),max(0,min(size[1]-layer.height,int(y*size[1]-layer.height/2)))))
    if stage=='oeuf':
        egg=_asset_image(root/'eggs'/f"{pet.get('color','bleu')}.webp")
        if egg.is_file():
            # Œuf illustré : image complète (fond galactique inclus), sans accessoires.
            with Image.open(egg) as egg_img:
                egg_img=egg_img.convert('RGB').resize(size,Image.Resampling.LANCZOS)
                result=io.BytesIO();egg_img.save(result,format='PNG');result.seek(0)
                return result
    if character.is_file():
        with Image.open(character) as source:
            layer=source.convert('RGBA')
            layer.thumbnail((int(size[0]*.65),int(size[1]*.78)),Image.Resampling.LANCZOS)
            canvas.alpha_composite(layer,((size[0]-layer.width)//2,int(size[1]*.88)-layer.height))
    elif stage not in ('adolescent','adulte'):
        # Missing asset: do not pretend another life stage is the correct one.
        return render(pet,stage=stage,mood=mood,theme='cosmos',size=(760,440))
    out=io.BytesIO();canvas.convert('RGB').save(out,format='PNG');out.seek(0);return out


def compose_walk(pet, code, stage='nouveau_ne', mood='heureux', size=(1280,720)):
    """Return PNG with the member's own NOX over the matching story landscape."""
    from PIL import Image, ImageEnhance
    base=_asset_image(Path(__file__).resolve().parent.parent/'assets'/'nox_junior'/'walks'/f'{code}.webp')
    if code not in ('prairie','etoiles','plage','jardin','foret','automne','hiver') or not base.is_file():
        raise ValueError('Unknown walk background')
    canvas=Image.open(base).convert('RGBA').resize(size,Image.Resampling.LANCZOS)
    color=str(pet.get('color','bleu'))
    if color not in PALETTE:raise ValueError('Unknown color')
    asset=_character_asset(Path(__file__).resolve().parent.parent/'data'/'nox_junior',stage,color,mood)
    if asset.is_file():
        layer=Image.open(asset).convert('RGBA')
        layer.thumbnail((int(size[0]*.35),int(size[1]*.68)),Image.Resampling.LANCZOS)
        x=int(size[0]*.50-layer.width/2);y=int(size[1]*.91-layer.height)
        canvas.alpha_composite(layer,(x,y))
    else:
        # Existing renderer remains functional for egg/baby stages lacking cutouts.
        fallback=render(pet,stage=stage,mood=mood,theme='cosmos',size=(760,440))
        # Do not paste an opaque fallback box over the scenery.
    out=io.BytesIO();canvas.convert('RGB').save(out,format='PNG',optimize=True);out.seek(0);return out
