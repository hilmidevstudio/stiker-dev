import 'package:flutter/material.dart';

/// Centralized Apple Human Interface Guidelines (HIG) Design Tokens
/// Provides consistent colors, typography, surfaces, metrics, and radii.
class IosTokens {
  IosTokens._();

  // ---------------------------------------------------------------------------
  // Color Palette (Apple HIG System Colors)
  // ---------------------------------------------------------------------------
  static const Color systemBackground = Color(0xFFFFFFFF);
  static const Color systemGroupedBackground = Color(0xFFF2F2F7);
  static const Color secondaryGroupedBackground = Color(0xFFFFFFFF);
  static const Color tertiaryGroupedBackground = Color(0xFFF9F9FB);

  // Labels & Text Hierarchy
  static const Color label = Color(0xFF000000);
  static const Color secondaryLabel = Color(0xFF8E8E93);
  static const Color tertiaryLabel = Color(0xFFC7C7CC);
  static const Color quaternaryLabel = Color(0xFFD1D1D6);

  // Separators & Borders
  static const Color separator = Color(0xFFC6C6C8);
  static const Color hairline = Color(0xFFE5E5EA);

  // Accents & Semantic Tints
  static const Color tint = Color(0xFF007AFF); // Apple System Blue
  static const Color success = Color(0xFF34C759); // Apple System Green
  static const Color destructive = Color(0xFFFF3B30); // Apple System Red
  static const Color warning = Color(0xFFFF9500); // Apple System Orange
  static const Color whatsApp = Color(0xFF25D366); // WhatsApp Official Green

  // Neutral fills
  static const Color secondarySystemFill = Color(0xFFEFEFF0);
  static const Color tertiarySystemFill = Color(0xFFE5E5EA);

  // ---------------------------------------------------------------------------
  // Typography Hierarchy (Human Interface Guidelines Scale)
  // ---------------------------------------------------------------------------
  static const TextStyle largeTitle = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.6,
    color: label,
  );

  static const TextStyle title1 = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.4,
    color: label,
  );

  static const TextStyle title2 = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.3,
    color: label,
  );

  static const TextStyle title3 = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
    color: label,
  );

  static const TextStyle sectionHeader = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.1,
    color: secondaryLabel,
  );

  static const TextStyle body = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.2,
    height: 1.35,
    color: label,
  );

  static const TextStyle callout = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.2,
    color: label,
  );

  static const TextStyle subheadline = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.1,
    color: secondaryLabel,
  );

  static const TextStyle footnote = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.0,
    color: secondaryLabel,
  );

  static const TextStyle caption1 = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.1,
    color: secondaryLabel,
  );

  static const TextStyle button = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
    color: Colors.white,
  );

  // ---------------------------------------------------------------------------
  // Radii & Continuous Corner Styling
  // ---------------------------------------------------------------------------
  static const double radiusSm = 6.0;
  static const double radiusMd = 10.0;
  static const double radiusLg = 14.0;
  static const double radiusCard = 16.0;
  static const double radiusSheet = 20.0;
  static const double radiusPill = 999.0;

  // ---------------------------------------------------------------------------
  // Spacing Scale
  // ---------------------------------------------------------------------------
  static const double spaceXs = 4.0;
  static const double spaceSm = 8.0;
  static const double spaceMd = 12.0;
  static const double spaceLg = 16.0;
  static const double spaceXl = 20.0;
  static const double spaceXxl = 24.0;
  static const double spaceSection = 32.0;

  // ---------------------------------------------------------------------------
  // Shadows (Soft, Apple-style subtle ambient elevation)
  // ---------------------------------------------------------------------------
  static List<BoxShadow> get cardShadow => [
        BoxShadow(
          color: Colors.black.withOpacity(0.02),
          blurRadius: 10,
          offset: const Offset(0, 2),
        ),
      ];

  static List<BoxShadow> get sheetShadow => [
        BoxShadow(
          color: Colors.black.withOpacity(0.08),
          blurRadius: 20,
          offset: const Offset(0, -4),
        ),
      ];
}
