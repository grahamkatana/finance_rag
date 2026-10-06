package com.graham_katana.financerag.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

// The same palette as the web app: a near-black oxblood ground and banker's green.
// Dark only, so the two apps read as one product.
private val Ground = Color(0xFF120B0D)
private val Surface = Color(0xFF1B1215)
private val SurfaceHigh = Color(0xFF241A1E)
private val Paper = Color(0xFFEDE8E0)
private val Muted = Color(0xFFA39D95)
private val Outline = Color(0xFF3A2D31)
// The one green. It is a fill only (title bar, buttons, your own messages); it is too dark to read
// as text on the ground colour, so text is always paper or muted.
val Green = Color(0xFF2C6E49)

private val Scheme = darkColorScheme(
    primary = Green,
    onPrimary = Color.White,
    primaryContainer = SurfaceHigh,
    onPrimaryContainer = Paper,
    secondaryContainer = SurfaceHigh,
    onSecondaryContainer = Paper,
    background = Ground,
    onBackground = Paper,
    surface = Surface,
    onSurface = Paper,
    surfaceVariant = SurfaceHigh,
    onSurfaceVariant = Muted,
    surfaceContainer = Surface,
    surfaceContainerHigh = SurfaceHigh,
    outline = Outline,
    outlineVariant = Outline,
    error = Color(0xFFFF8A80),
)

// Text fields use the theme's smallest shape. Rounding it brings them in line with the pill buttons;
// menus share the shape and look right with it too.
private val AppShapes = Shapes(extraSmall = RoundedCornerShape(16.dp))

@Composable
fun FinanceRagTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Scheme, shapes = AppShapes, content = content)
}
