import { Pressable, Text, View } from 'react-native';

import { schStyles as styles } from './schedule-styles';
import { addDays, weekLabel } from './schedule-utils';

type Props = {
  weekStart: Date;
  selected: Date;
  /** Number of agenda items per day index (0 = Monday). */
  counts: number[];
  onSelect: (d: Date) => void;
  onShiftWeek: (delta: number) => void;
  onToday: () => void;
};

export function WeekStrip({ weekStart, selected, counts, onSelect, onShiftWeek, onToday }: Props) {
  const today = new Date();
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  return (
    <View>
      <View style={styles.weekNav}>
        <Pressable style={styles.weekNavButton} onPress={() => onShiftWeek(-1)} accessibilityRole="button" accessibilityLabel="Previous week">
          <Text style={styles.weekNavText}>‹</Text>
        </Pressable>
        <View>
          <Text style={styles.weekLabel}>{weekLabel(weekStart)}</Text>
          <Pressable onPress={onToday} accessibilityRole="button" accessibilityLabel="Go to today">
            <Text style={styles.todayLink}>Today</Text>
          </Pressable>
        </View>
        <Pressable style={styles.weekNavButton} onPress={() => onShiftWeek(1)} accessibilityRole="button" accessibilityLabel="Next week">
          <Text style={styles.weekNavText}>›</Text>
        </Pressable>
      </View>
      <View style={styles.dayRow}>
        {Array.from({ length: 7 }, (_, i) => {
          const day = addDays(weekStart, i);
          const active = same(day, selected);
          const count = counts[i] ?? 0;
          return (
            <Pressable
              key={i}
              style={[styles.dayChip, same(day, today) && styles.dayChipToday, active && styles.dayChipActive]}
              onPress={() => onSelect(day)}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`${day.toDateString()}, ${count} visit${count === 1 ? '' : 's'}`}
            >
              <Text style={[styles.dayName, active && styles.dayTextActive]}>
                {day.toLocaleDateString('en-IN', { weekday: 'short' })}
              </Text>
              <Text style={[styles.dayNumber, active && styles.dayTextActive]}>{day.getDate()}</Text>
              <View style={[styles.dayDot, count === 0 && styles.dayDotEmpty]} />
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
