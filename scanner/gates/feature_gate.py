"""Scanner v3 - Feature Gate

@module quro.scanner.gates.feature_gate
@intent Validate and cap feature lists
@constraint Pure function, transform gate (returns modified data)
"""

from typing import Tuple
from scanner.types import SymbolFeatures
from scanner.gates.types import GateResult


class FeatureGate:
    """Feature validation and capping gate.

    Transform gate: May modify features (cap to max count).

    Validates:
    - Feature count limits
    - Feature name format
    - Duplicate features
    """

    # Maximum features per symbol
    MAX_FEATURES = 100

    @staticmethod
    def validate(features: SymbolFeatures) -> GateResult:
        """Validate and cap features.

        Transform gate: Returns modified_data if features capped.

        Args:
            features: Symbol features to validate

        Returns:
            GateResult with modified_data if capped
        """
        total_features = (
            len(features.behavioral_tags)
            + len(features.structural_tags)
            + len(features.risk_anchors)
        )

        # Check if capping needed
        if total_features > FeatureGate.MAX_FEATURES:
            # Cap features (prioritize: risk > behavioral > structural)
            capped = FeatureGate._cap_features(features)

            return GateResult(
                passed=True,
                reason="features_capped",
                modified_data={"features": capped},
                metadata={
                    "original_count": total_features,
                    "capped_count": FeatureGate.MAX_FEATURES,
                },
            )

        # No capping needed
        return GateResult(passed=True)

    @staticmethod
    def _cap_features(features: SymbolFeatures) -> SymbolFeatures:
        """Cap features to MAX_FEATURES.

        Priority: risk_anchors > behavioral_tags > structural_tags

        Args:
            features: Original features

        Returns:
            Capped features
        """
        # Calculate budget for each category
        risk_count = min(len(features.risk_anchors), FeatureGate.MAX_FEATURES // 3)
        remaining = FeatureGate.MAX_FEATURES - risk_count

        behavioral_count = min(len(features.behavioral_tags), remaining // 2)
        remaining -= behavioral_count

        structural_count = min(len(features.structural_tags), remaining)

        # Cap each category
        return SymbolFeatures(
            behavioral_tags=features.behavioral_tags[:behavioral_count],
            structural_tags=features.structural_tags[:structural_count],
            risk_anchors=features.risk_anchors[:risk_count],
            lsh_signature=features.lsh_signature,
        )

    @staticmethod
    def validate_tag_format(tag: str) -> bool:
        """Validate tag format.

        Tags must be:
        - Lowercase
        - Alphanumeric + underscore
        - 2-50 characters

        Args:
            tag: Tag string to validate

        Returns:
            True if valid format
        """
        if not tag:
            return False

        if len(tag) < 2 or len(tag) > 50:
            return False

        if not tag.islower():
            return False

        # Check alphanumeric + underscore
        return all(c.isalnum() or c == "_" for c in tag)

    @staticmethod
    def deduplicate_features(features: SymbolFeatures) -> SymbolFeatures:
        """Remove duplicate features.

        Args:
            features: Features with potential duplicates

        Returns:
            Features with duplicates removed
        """
        return SymbolFeatures(
            behavioral_tags=tuple(sorted(set(features.behavioral_tags))),
            structural_tags=tuple(sorted(set(features.structural_tags))),
            risk_anchors=tuple(sorted(set(features.risk_anchors))),
            lsh_signature=features.lsh_signature,
        )
