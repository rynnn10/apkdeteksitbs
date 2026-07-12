plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.kotlin.android)
  alias(libs.plugins.kotlin.compose)
}

android {
  namespace = "com.tbsdeteksi"
  compileSdk = 36

  defaultConfig {
    applicationId = "com.tbsdeteksi.kelapa.sawit"
    minSdk = 24
    targetSdk = 36
    versionCode = 1
    versionName = "1.0.0"

    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    buildConfigField("String", "BUILD_TIMESTAMP", "\"${System.currentTimeMillis()}\"")
  }

  signingConfigs {
    create("release") {
      // Release signing: set env KEYSTORE_PATH, STORE_PASSWORD, KEY_PASSWORD
            val ksPath = System.getenv("KEYSTORE_PATH") ?: project.findProperty("KEYSTORE_PATH")?.toString()
      val ksStorePass = System.getenv("STORE_PASSWORD") ?: project.findProperty("STORE_PASSWORD")?.toString()
      val ksKeyPass = System.getenv("KEY_PASSWORD") ?: project.findProperty("KEY_PASSWORD")?.toString()

      if (ksPath != null && ksStorePass != null && ksKeyPass != null) {
        storeFile = file(ksPath)
        storePassword = ksStorePass
        keyAlias = "upload"
        keyPassword = ksKeyPass
      } else {
        logger.warn("Release signing not configured. Set KEYSTORE_PATH, STORE_PASSWORD, KEY_PASSWORD.")
      }
    }
    create("debugConfig") {
      storeFile = file("../debug.keystore")
      storePassword = "android"
      keyAlias = "androiddebugkey"
      keyPassword = "android"
    }
  }

  buildTypes {
    release {
      isMinifyEnabled = false
      proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
      signingConfig = signingConfigs.getByName("release")
    }
    debug {
      signingConfig = signingConfigs.getByName("debugConfig")
    }
  }

  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_11
    targetCompatibility = JavaVersion.VERSION_11
  }

  kotlinOptions {
    jvmTarget = "11"
  }

  buildFeatures {
    compose = true
    buildConfig = true
  }

  lint {
    abortOnError = false
    checkReleaseBuilds = false
  }

  testOptions {
    unitTests {
      isIncludeAndroidResources = true
    }
  }
}

dependencies {
  implementation(platform(libs.androidx.compose.bom))
  implementation(libs.androidx.activity.compose)
  implementation(libs.androidx.compose.material.icons.core)
  implementation(libs.androidx.compose.material3)
  implementation(libs.androidx.compose.ui)
  implementation(libs.androidx.compose.ui.graphics)
  implementation(libs.androidx.compose.ui.tooling.preview)
  implementation(libs.androidx.core.ktx)
  implementation(libs.androidx.lifecycle.runtime.compose)
  implementation(libs.androidx.lifecycle.runtime.ktx)
  implementation(libs.androidx.lifecycle.viewmodel.compose)
  implementation(libs.kotlinx.coroutines.android)
  implementation(libs.kotlinx.coroutines.core)

  testImplementation(libs.androidx.compose.ui.test.junit4)
  testImplementation(libs.androidx.core)
  testImplementation(libs.androidx.junit)
  testImplementation(libs.junit)
  testImplementation(libs.kotlinx.coroutines.test)

  androidTestImplementation(platform(libs.androidx.compose.bom))
  androidTestImplementation(libs.androidx.compose.ui.test.junit4)
  androidTestImplementation(libs.androidx.espresso.core)
  androidTestImplementation(libs.androidx.junit)
  androidTestImplementation(libs.androidx.runner)

  debugImplementation(libs.androidx.compose.ui.test.manifest)
  debugImplementation(libs.androidx.compose.ui.tooling)
}

// Custom task: reinstall debug APK
val baseAppId = "com.tbsdeteksi.kelapa.sawit"
val debugAppId = "$baseAppId.debug"

val deviceId: String? = if (project.hasProperty("deviceId")) {
  project.property("deviceId").toString()
} else null

fun adbCommand(vararg args: String): List<String> {
  return if (deviceId.isNullOrBlank()) {
    listOf("adb", *args)
  } else {
    listOf("adb", "-s", deviceId, *args)
  }
}

val uninstallBase = tasks.register<Exec>("adbUninstallBase") {
  isIgnoreExitValue = true
  commandLine = adbCommand("uninstall", baseAppId)
}

val uninstallDebug = tasks.register<Exec>("adbUninstallDebug") {
  isIgnoreExitValue = true
  commandLine = adbCommand("uninstall", debugAppId)
}

val installApk = tasks.register<Exec>("adbInstallDebugApk") {
  dependsOn("assembleDebug")
  val apkPath = "${layout.buildDirectory.get().asFile}/outputs/apk/debug/app-debug.apk"
  doFirst {
    val apk = file(apkPath)
    if (!apk.exists()) {
      throw GradleException("Debug APK not found: ${apk.absolutePath}")
    }
  }
  commandLine = adbCommand("install", "-r", apkPath)
}

tasks.register("reinstallDebug") {
  dependsOn(uninstallBase, uninstallDebug, installApk)
}
