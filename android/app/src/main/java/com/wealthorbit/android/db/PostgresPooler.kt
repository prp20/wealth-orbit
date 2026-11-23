package com.wealthorbit.android.db

import java.sql.Connection
import java.sql.DriverManager
import java.util.Properties

object PostgresPooler {
    fun open(poolerUrl: String): Connection {
        Class.forName("org.postgresql.Driver")
        var url = poolerUrl.trim()
        if (!url.startsWith("jdbc:")) {
            url = "jdbc:$url"
        }
        if (!url.contains("sslmode=")) {
            url += if (url.contains("?")) "&sslmode=require" else "?sslmode=require"
        }
        val props = Properties().apply {
            setProperty("loginTimeout", "15")
            setProperty("connectTimeout", "15")
            setProperty("socketTimeout", "60")
            setProperty("ApplicationName", "wealth-orbit-android")
        }
        return DriverManager.getConnection(url, props)
    }
}
