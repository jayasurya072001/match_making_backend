NORMALIZATION_MAP = {
    "curly hairs": "curly",
    "curly hair": "curly",
    "curly-haired": "curly",
    "wavy hairs": "wavy",
    "straight hairs": "straight",
    "male person": "male",
    "female person": "female"
}

def normalize_value(value: str) -> str:
    v = value.lower().strip()
    return NORMALIZATION_MAP.get(v, v)


def build_filters(attrs: ImageAttributes) -> dict:
    filters = {}

    def add(key, value):
        if value is not None:
            filters[key] = value

    add("gender", attrs.gender)
    add("ethnicity", attrs.ethnicity)
    add("age_group", attrs.age_group)
    add("eye_color", attrs.eye_color)

    if attrs.hair:
        add("hair_color", attrs.hair.hair_color)
        add("hair_style", attrs.hair.hair_style)

    if attrs.accessories:
        add("eyewear", attrs.accessories.eyewear)
        add("headwear", attrs.accessories.headwear)

    return filters
