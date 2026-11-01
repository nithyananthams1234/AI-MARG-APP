import { usePathname, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { MargColors } from '@/constants/theme';

const navigationItems = [
  { label: 'Home', path: '/dashboard', icon: '⌂' },
  { label: 'Schools', path: '/schools', icon: '▦' },
  { label: 'Tasks', path: '/tasks', icon: '✓' },
  { label: 'Coach', path: '/classroom-coach', icon: '✦' },
  { label: 'Schedule', path: '/schedule', icon: '▦' },
  { label: 'Profile', path: '/profile', icon: '○' },
] as const;

export default function BottomNavigation() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <View style={styles.navigation} accessibilityRole="tablist">
      {navigationItems.map((item) => {
        const selected =
          item.label === 'Home'
            ? pathname === '/dashboard'
            : pathname === item.path ||
              pathname.startsWith(`${item.path}/`) ||
              (item.label === 'Schedule' && pathname.startsWith('/visits'));

        return (
          <Pressable
            key={item.path}
            style={styles.item}
            onPress={() => router.replace(item.path)}
            accessibilityRole="tab"
            accessibilityLabel={item.label}
            accessibilityState={{ selected }}
          >
            <Text style={[styles.icon, selected && styles.selectedText]}>
              {item.icon}
            </Text>
            <Text style={[styles.label, selected && styles.selectedText]}>
              {item.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  navigation: {
    height: 64,
    backgroundColor: MargColors.surface,
    borderTopWidth: 1,
    borderTopColor: MargColors.border,
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingHorizontal: 5,
  },
  item: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  icon: {
    color: MargColors.secondaryText,
    fontSize: 20,
  },
  label: {
    color: MargColors.secondaryText,
    fontSize: 9,
    fontWeight: '600',
  },
  selectedText: {
    color: MargColors.tealDark,
    fontWeight: '800',
  },
});
