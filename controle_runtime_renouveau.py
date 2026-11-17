"""Précontrôle des dépendances réellement importables, sans lancer le bot."""
import importlib
import sys

MODULES = {
    "discord.py": "discord",
    "python-dotenv": "dotenv",
    "aiohttp": "aiohttp",
    "Pillow": "PIL",
    "tzdata": "tzdata",
}
missing = []
for package, module in MODULES.items():
    try:
        imported = importlib.import_module(module)
        version = getattr(imported, "__version__", "version non exposée")
        print(f"OK      {package}: {version}")
    except (ImportError, Exception) as exc:
        missing.append(package)
        print(f"ABSENT  {package}: {type(exc).__name__}: {exc}")
if missing:
    print("\nPrécontrôle incomplet : installer les dépendances dans un environnement isolé :")
    print("python -m pip install -r requirements.txt")
    sys.exit(2)
print("\nDépendances importables : OK. Le démarrage Discord reste à tester.")
