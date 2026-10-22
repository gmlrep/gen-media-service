from gen_media_service.model.catalog import ModelLeg


def _leg(provider: str, priority: int, max_ref: int, skip: bool = False) -> ModelLeg:
    leg = ModelLeg(
        provider=provider,
        priority=priority,
        max_ref_images=max_ref,
        skip_on_moderation=skip,
    )
    return leg


def test_filter_legs_by_ref_count() -> None:
    legs = [
        _leg("alpha", 1, 4),
        _leg("beta", 2, 10),
    ]
    suitable = [leg for leg in legs if leg.max_ref_images >= 5]
    assert len(suitable) == 1
    assert suitable[0].provider == "beta"


def test_skip_on_moderation_filter() -> None:
    legs = [
        _leg("beta", 1, 2, skip=False),
        _leg("alpha", 2, 1, skip=True),
    ]
    after_moderation = True
    start = 1
    chosen = []
    index = start
    while index < len(legs):
        leg = legs[index]
        if after_moderation and leg.skip_on_moderation:
            index += 1
            continue
        chosen.append(leg.provider)
        break
    assert chosen == []
