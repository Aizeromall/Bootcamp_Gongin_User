import java.util.Properties
import java.util.Base64

plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.bootcamp_project_gongin_admin_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.example.bootcamp_project_gongin_admin_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // 수정 일 : 2026-10-28 / 작업자 : 최현준
        // 실제 값은 Git 제외된 android/local.properties에서 읽습니다.
        val socialProperties = Properties()
        val socialFile = rootProject.file("local.properties")
        if (socialFile.exists()) socialFile.inputStream().use { socialProperties.load(it) }
        val dartSettings = (project.findProperty("dart-defines") as? String)
            ?.split(",")?.mapNotNull { encoded ->
                val decoded = String(Base64.getDecoder().decode(encoded), Charsets.UTF_8)
                val separator = decoded.indexOf('=')
                if (separator < 0) null else decoded.substring(0, separator) to decoded.substring(separator + 1)
            }?.toMap() ?: emptyMap()
        manifestPlaceholders["kakaoNativeAppKey"] = dartSettings["KAKAO_NATIVE_APP_KEY"]
            ?: socialProperties.getProperty("KAKAO_NATIVE_APP_KEY", "not-configured")
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
