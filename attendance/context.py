def theme_for(sport) -> dict:
    palettes = {
        "tennis": {
            "hero": "from-emerald-900 via-emerald-700 to-lime-700",
        },
        "cricket": {
            "hero": "from-teal-950 via-teal-800 to-amber-700",
        },
    }
    return palettes.get(getattr(sport, "slug", ""), palettes["tennis"])


def page_ctx(request, **extra):
    staff = request.facility_manager
    sport = request.managed_sport
    ctx = {
        "sport": sport,
        "manager": staff,
        "managed_venues": getattr(request, "managed_venues", []),
        "can_manage_students": staff.can_manage_students(),
        "can_bill": staff.can_bill(),
        "theme": theme_for(sport),
    }
    ctx.update(extra)
    return ctx
