import { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MargColors as C } from '@/constants/theme';
import { useAuth } from '@/stores/auth';

export default function LoginScreen() {
  const signIn = useAuth((st) => st.signIn);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    // Check whether both fields are filled
    if (!email.trim() || !password.trim()) {
      Alert.alert(
        'Missing details',
        'Please enter your email and password.'
      );
      return;
    }

    // Validate email format
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      Alert.alert(
        'Invalid email',
        'Please enter a valid email address.'
      );
      return;
    }

    // Authenticate against the MARG backend; the root layout redirects
    // to the dashboard once the session is established.
    setError(null);
    setLoading(true);
    try {
      await signIn(email.trim(), password);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.container}>
            {/* Brand */}
            <View style={styles.brandSection}>
              <View style={styles.logo}>
                <Text style={styles.logoLetter}>M</Text>
              </View>

              <Text style={styles.brandName}>MARG</Text>
              <Text style={styles.brandSubtitle}>
                Mentoring. Action. Reflection. Growth.
              </Text>
            </View>

            {/* Welcome */}
            <View style={styles.welcomeSection}>
              <Text style={styles.welcomeTitle}>Welcome back</Text>
              <Text style={styles.welcomeDescription}>
                Sign in to continue your mentoring journey and manage your
                assigned schools.
              </Text>
            </View>

            {/* Login Card */}
            <View style={styles.card}>
              <View style={styles.cardHeading}>
                <Text style={styles.cardTitle}>Mentor Login</Text>

                <View style={styles.roleBadge}>
                  <View style={styles.roleDot} />
                  <Text style={styles.roleText}>MENTOR ACCESS</Text>
                </View>
              </View>

              <Text style={styles.label}>Email address</Text>

              <View style={styles.inputContainer}>
                <Text style={styles.inputIcon}>@</Text>

                <TextInput
                  style={styles.input}
                  placeholder="Enter your email"
                  placeholderTextColor={C.muted}
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  textContentType="emailAddress"
                  returnKeyType="next"
                />
              </View>

              <Text style={[styles.label, styles.passwordLabel]}>
                Password
              </Text>

              <View style={styles.inputContainer}>
                <Text style={styles.lockIcon}>●</Text>

                <TextInput
                  style={styles.input}
                  placeholder="Enter your password"
                  placeholderTextColor={C.muted}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  textContentType="password"
                  returnKeyType="done"
                  onSubmitEditing={handleLogin}
                />

                <Pressable
                  onPress={() => setShowPassword(!showPassword)}
                  hitSlop={10}
                  accessibilityRole="button"
                  accessibilityLabel={
                    showPassword ? 'Hide password' : 'Show password'
                  }
                >
                  <Text style={styles.showPassword}>
                    {showPassword ? 'Hide' : 'Show'}
                  </Text>
                </Pressable>
              </View>

              {error ? (
                <Text style={styles.errorText} accessibilityRole="alert">
                  {error}
                </Text>
              ) : null}

              <Pressable
                style={({ pressed }) => [
                  styles.loginButton,
                  pressed && styles.buttonPressed,
                  loading && styles.buttonDisabled,
                ]}
                onPress={handleLogin}
                disabled={loading}
              >
                <Text style={styles.loginButtonText}>
                  {loading ? 'Signing in...' : 'Sign in'}
                </Text>

                {!loading && (
                  <Text style={styles.arrow}>→</Text>
                )}
              </Pressable>

              <Text style={styles.secureNote}>
                Your mentoring workspace is protected by secure account access.
              </Text>
            </View>

            {/* Access information */}
            <View style={styles.infoCard}>
              <View style={styles.infoIconContainer}>
                <Text style={styles.infoIcon}>✦</Text>
              </View>

              <View style={styles.infoContent}>
                <Text style={styles.infoTitle}>
                  One mentor. Multiple schools.
                </Text>

                <Text style={styles.infoDescription}>
                  Access your assigned schools, visits, classroom observations,
                  follow-ups and mentoring activities in one place.
                </Text>
              </View>
            </View>

            {/* Footer */}
            <View style={styles.footer}>
              <Text style={styles.footerText}>
                MARG · Intelligent Educational Mentoring
              </Text>

              <Text style={styles.versionText}>Version 1.0.0</Text>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  errorText: {
    color: C.danger,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    textAlign: 'center',
  },
  flex: {
    flex: 1,
  },

  safeArea: {
    flex: 1,
    backgroundColor: C.background,
  },

  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingVertical: 28,
  },

  container: {
    width: '100%',
    maxWidth: 460,
    alignSelf: 'center',
    paddingHorizontal: 24,
  },

  brandSection: {
    alignItems: 'center',
    marginBottom: 38,
  },

  logo: {
    width: 62,
    height: 62,
    borderRadius: 20,
    backgroundColor: C.navy,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
    shadowColor: C.navy,
    shadowOpacity: 0.2,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 5,
  },

  logoLetter: {
    color: '#FFFFFF',
    fontSize: 34,
    fontWeight: '800',
  },

  brandName: {
    color: C.navy,
    fontSize: 25,
    fontWeight: '800',
    letterSpacing: 5,
  },

  brandSubtitle: {
    color: C.secondaryText,
    fontSize: 11,
    marginTop: 6,
    letterSpacing: 0.6,
  },

  welcomeSection: {
    marginBottom: 24,
  },

  welcomeTitle: {
    color: C.text,
    fontSize: 29,
    fontWeight: '800',
    letterSpacing: -0.8,
  },

  welcomeDescription: {
    color: C.secondaryText,
    fontSize: 14,
    lineHeight: 22,
    marginTop: 9,
  },

  card: {
    backgroundColor: C.surface,
    borderRadius: 22,
    padding: 23,
    borderWidth: 1,
    borderColor: C.border,
    shadowColor: '#18324F',
    shadowOpacity: 0.06,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    elevation: 3,
  },

  cardHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 27,
    flexWrap: 'wrap',
    gap: 10,
  },

  cardTitle: {
    color: C.text,
    fontSize: 19,
    fontWeight: '800',
  },

  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EAF8F6',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 7,
    gap: 6,
  },

  roleDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: C.teal,
  },

  roleText: {
    color: C.tealDark,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.6,
  },

  label: {
    color: C.text,
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 9,
  },

  passwordLabel: {
    marginTop: 20,
  },

  inputContainer: {
    height: 54,
    borderRadius: 12,
    backgroundColor: C.inputBackground,
    borderWidth: 1,
    borderColor: C.border,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
  },

  inputIcon: {
    color: C.teal,
    fontSize: 20,
    fontWeight: '700',
    marginRight: 11,
  },

  lockIcon: {
    color: C.teal,
    fontSize: 11,
    marginRight: 15,
  },

  input: {
    flex: 1,
    height: '100%',
    color: C.text,
    fontSize: 14,
  },

  showPassword: {
    color: C.tealDark,
    fontSize: 12,
    fontWeight: '700',
    paddingLeft: 8,
  },

  loginButton: {
    height: 55,
    backgroundColor: C.navy,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    marginTop: 27,
    shadowColor: C.navy,
    shadowOpacity: 0.17,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 },
    elevation: 3,
  },

  buttonPressed: {
    opacity: 0.85,
    transform: [{ scale: 0.99 }],
  },

  buttonDisabled: {
    opacity: 0.65,
  },

  loginButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },

  arrow: {
    color: '#FFFFFF',
    fontSize: 21,
    position: 'absolute',
    right: 20,
  },

  secureNote: {
    color: C.secondaryText,
    fontSize: 10,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: 17,
  },

  infoCard: {
    flexDirection: 'row',
    backgroundColor: '#EAF5F5',
    borderRadius: 15,
    padding: 16,
    marginTop: 20,
    gap: 12,
    borderWidth: 1,
    borderColor: '#D9ECEA',
  },

  infoIconContainer: {
    width: 34,
    height: 34,
    borderRadius: 11,
    backgroundColor: '#D3EEEA',
    alignItems: 'center',
    justifyContent: 'center',
  },

  infoIcon: {
    color: C.tealDark,
    fontSize: 19,
  },

  infoContent: {
    flex: 1,
  },

  infoTitle: {
    color: C.navy,
    fontSize: 12,
    fontWeight: '800',
    marginBottom: 5,
  },

  infoDescription: {
    color: C.secondaryText,
    fontSize: 11,
    lineHeight: 17,
  },

  footer: {
    alignItems: 'center',
    marginTop: 30,
    gap: 5,
  },

  footerText: {
    color: C.secondaryText,
    fontSize: 10,
    fontWeight: '600',
  },

  versionText: {
    color: C.muted,
    fontSize: 10,
  },
});
