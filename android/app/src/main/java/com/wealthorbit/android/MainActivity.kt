package com.wealthorbit.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.wealthorbit.android.ui.agent.AgentScreen
import com.wealthorbit.android.ui.home.HomeScreen
import com.wealthorbit.android.ui.portfolio.PortfolioScreen
import com.wealthorbit.android.ui.settings.SettingsScreen
import com.wealthorbit.android.ui.setup.SetupScreen
import com.wealthorbit.android.ui.theme.WealthOrbitTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            WealthOrbitTheme {
                WealthOrbitApp()
            }
        }
    }
}

private enum class Dest(
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    Home("home", "Home", Icons.Outlined.Home),
    Portfolio("portfolio", "Portfolio", Icons.Outlined.AccountBalanceWallet),
    Agent("agent", "Agent", Icons.Outlined.Psychology),
    Settings("settings", "Settings", Icons.Outlined.Settings),
}

@Composable
fun WealthOrbitApp() {
    val navController = rememberNavController()
    val backStack by navController.currentBackStackEntryAsState()
    val current = backStack?.destination
    val showBar = Dest.entries.any { dest ->
        current?.hierarchy?.any { it.route == dest.route } == true
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        bottomBar = {
            if (showBar) {
                NavigationBar {
                    Dest.entries.forEach { dest ->
                        NavigationBarItem(
                            selected = current?.hierarchy?.any { it.route == dest.route } == true,
                            onClick = {
                                navController.navigate(dest.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(dest.icon, contentDescription = dest.label) },
                            label = { Text(dest.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = "setup",
            modifier = Modifier.padding(padding),
        ) {
            composable("setup") {
                SetupScreen(
                    onConfigured = {
                        navController.navigate(Dest.Home.route) {
                            popUpTo("setup") { inclusive = true }
                        }
                    },
                )
            }
            composable(Dest.Home.route) { HomeScreen() }
            composable(Dest.Portfolio.route) { PortfolioScreen() }
            composable(Dest.Agent.route) { AgentScreen() }
            composable(Dest.Settings.route) {
                SettingsScreen(
                    onOpenSetup = { navController.navigate("setup") },
                )
            }
        }
    }
}
