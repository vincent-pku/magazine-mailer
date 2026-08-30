from typing import Protocol

from magazine_mailer.models import Issue, MagazineSpec


class MagazineSource(Protocol):
    def latest_issue(self, magazine: MagazineSpec) -> Issue:
        ...
