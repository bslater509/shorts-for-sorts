import json

print("XTTSv2 supports many voices, but we use the built-in speaker profiles.")
print("The list of default speakers available in the XTTSv2 model:")
voices = [
    "Claribel Dervla", "Daisy Studious", "Gracie Wise", "Tammie Ema", "Alison DietI", "Ana Florence",
    "Annmarie Nele", "Asya Anara", "Brenda Stern", "Gitta Nikolina", "Henriette Usha", "Sofia Hellen",
    "Tammy Grit", "Tanya Linda", "Zacharie Julian", "Badr Odhiambo", "Craig Gutsy", "Damien Black",
    "Jared Fakhri", "Marvelous Chau", "Rocco Venda"
]
for v in voices:
    print(f"- {v}")

print("Loaded modules.")
