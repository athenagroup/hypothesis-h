from h.presenters.annotation_base import AnnotationBasePresenter
from h.util.datetime import utc_iso8601


class AnnotationJSONLDPresenter(AnnotationBasePresenter):
    """
    Presenter for annotations that renders JSON-LD.

    JSON-LD compatible with the draft Web Annotation Data Model, as defined at:

      https://www.w3.org/TR/annotation-model/
    """

    def __init__(self, annotation, links_service):
        super().__init__(annotation)

        self._links_service = links_service

    CONTEXT_URL = "http://www.w3.org/ns/anno.jsonld"

    def asdict(self):
        return {
            "@context": self.CONTEXT_URL,
            "type": "Annotation",
            "id": self._links_service.get(self.annotation, "jsonld_id"),
            "created": utc_iso8601(self.annotation.created),
            "modified": utc_iso8601(self.annotation.updated),
            "creator": self.annotation.userid,
            "body": self._bodies,
            "target": self._target,
        }

    @property
    def _bodies(self):
        bodies = [
            {
                "type": "TextualBody",
                "value": self.annotation.text or "",
                "format": "text/markdown",
            }
        ]
        if self.annotation.tags:
            for tag in self.annotation.tags:
                bodies.append(
                    {"type": "TextualBody", "value": tag, "purpose": "tagging"}
                )

        return bodies

    @property
    def _target(self):
        target = {"source": self.annotation.target_uri}
        selectors = []

        # Some selectors generated by our client aren't valid selectors from
        # the W3C Annotation model, and need remapping.
        #
        # Specifically, the RangeSelector that our client generates is not the
        # RangeSelector defined by the spec, which is a much more generic
        # object.
        #
        # Remap the RangeSelector, and drop any selectors which don't have a
        # named type.
        for selector in self.annotation.target_selectors:
            try:
                type_ = selector["type"]
            except KeyError:
                continue
            if type_ == "RangeSelector":
                selector = _convert_range_selector(selector)
                if selector is None:
                    continue
            selectors.append(selector)

        if selectors:
            target["selector"] = selectors

        return [target]


def _convert_range_selector(selector):
    """Convert an old-style range selector to the standard form."""

    is_range_selector = selector["type"] == "RangeSelector"
    has_start = "startContainer" in selector and "startOffset" in selector
    has_end = "endContainer" in selector and "endOffset" in selector

    if not (is_range_selector and has_start and has_end):
        return None

    # A RangeSelector that starts and ends in the same element should be
    # rewritten to an XPathSelector refinedBy a TextPositionSelector, for the
    # sake of simplicity.
    if selector["startContainer"] == selector["endContainer"]:
        return {
            "type": "XPathSelector",
            "value": selector["startContainer"],
            "refinedBy": {
                "type": "TextPositionSelector",
                "start": selector["startOffset"],
                "end": selector["endOffset"],
            },
        }

    # A RangeSelector that starts and ends in the different elements should be
    # rewritten to a RangeSelector bounded by two XPathSelectors, each of
    # which is refinedBy a "point"-like TextPositionSelector.
    #
    # This is ugly as sin, but I can't see a better way of doing this at the
    # moment.
    return {
        "type": "RangeSelector",
        "startSelector": {
            "type": "XPathSelector",
            "value": selector["startContainer"],
            "refinedBy": {
                "type": "TextPositionSelector",
                "start": selector["startOffset"],
                "end": selector["startOffset"],
            },
        },
        "endSelector": {
            "type": "XPathSelector",
            "value": selector["endContainer"],
            "refinedBy": {
                "type": "TextPositionSelector",
                "start": selector["endOffset"],
                "end": selector["endOffset"],
            },
        },
    }
