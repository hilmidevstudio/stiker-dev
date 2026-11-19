import 'package:flutter/material.dart';

/// Clean and aesthetic footer displaying branding
class AppFooter extends StatelessWidget {
  const AppFooter({super.key});

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 20.0),
      child: Center(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Made with ',
              style: TextStyle(
                fontSize: 12,
                color: Color(0xFF8E8E93),
                fontWeight: FontWeight.w400,
              ),
            ),
            Icon(
              Icons.favorite,
              size: 12,
              color: Color(0xFFFF3B30),
            ),
            Text(
              ' by ',
              style: TextStyle(
                fontSize: 12,
                color: Color(0xFF8E8E93),
                fontWeight: FontWeight.w400,
              ),
            ),
            Text(
              'hilmidev.studio',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Color(0xFF1C1C1E),
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
