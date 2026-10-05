package com.graham_katana.financerag.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// The same palette as the web app: a near-black oxblood ground and banker's green.
// Dark only, so the two apps read as one product.
private val Ground = Color(0xFF120B0D)
private val Surface = Color(0xFF1B1215)
private val SurfaceHigh = Color(0xFF241A1E)
private val Paper = Color(0xFFEDE8E0)
private val Muted = Color(0xFFA39D95)
private val Outline = Color(0xFF3A2D31)
val Green = Color(0xFF2C6E49)
val GreenText = Color(0xFF8FD6AE) // #2C6E49 is too dark to read as text on the ground colour
private val GreenTint = Color(0xFF17301F)
/** Title bar. Drawn under the status bar too (the app is edge-to-edge), so the two read as one strip. */
val TopBarGreen = Color(0xFF1F4D34)

private val Scheme = darkColorScheme(
    primary = Green,
    onPrimary = Color.White,
    primaryContainer = GreenTint,
    onPrimaryContainer = GreenText,
    secondaryContainer = GreenTint,
    onSecondaryContainer = GreenText,
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

@Composable
fun FinanceRagTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Scheme, content = content)
}
