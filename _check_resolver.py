from services.entity_resolver import normalize_name

cases = [
    ("Ramesh bhai", "Ramesh"),
    ("  suresh JI ", "Suresh"),
    ("MOHAN", "Mohan"),
    ("chhotu bhaiya", "Chhotu"),
    ("", ""),
]

for raw, expected in cases:
    got = normalize_name(raw)
    assert got == expected, f"normalize_name({raw!r}) -> {got!r}, expected {expected!r}"

# All-honorific edge case: should NOT return empty string
all_honorific = normalize_name("ji bhai")
assert all_honorific != "", f"All-honorific name returned empty: {all_honorific!r}"

print("Entity resolver normalization OK")
print(f'  ji bhai -> {all_honorific!r}')
