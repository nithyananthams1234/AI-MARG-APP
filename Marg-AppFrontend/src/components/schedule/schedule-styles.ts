import { StyleSheet } from 'react-native';

import { MargColors as C } from '@/constants/theme';

/** Shared styles for the schedule screen and its components (kept from the original screen design). */
export const schStyles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: C.background,
  },
  container: {
    padding: 20,
    paddingBottom: 40,
    maxWidth: 900,
    width: '100%',
    alignSelf: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  backButton: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  backText: {
    fontSize: 32,
    color: C.navy,
    marginTop: -5,
  },
  headerTitle: {
    flex: 1,
  },
  heading: {
    fontSize: 25,
    fontWeight: '800',
    color: C.navy,
  },
  subheading: {
    fontSize: 13,
    color: C.secondaryText,
    marginTop: 3,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 26,
  },
  summaryCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 15,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  summaryNumber: {
    fontSize: 25,
    fontWeight: '800',
    color: C.navy,
  },
  summaryLabel: {
    fontSize: 11,
    color: C.secondaryText,
    marginTop: 5,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 13,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: C.navy,
  },
  eventCount: {
    fontSize: 12,
    color: C.secondaryText,
  },
  filterRow: {
    gap: 8,
    paddingBottom: 15,
  },
  filterButton: {
    paddingHorizontal: 15,
    paddingVertical: 9,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: C.border,
  },
  activeFilter: {
    backgroundColor: C.navy,
    borderColor: C.navy,
  },
  filterText: {
    fontSize: 12,
    fontWeight: '600',
    color: C.secondaryText,
  },
  activeFilterText: {
    color: '#FFFFFF',
  },
  eventCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 13,
    borderWidth: 1,
    borderColor: C.border,
  },
  eventTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  typeIndicator: {
    width: 5,
    height: 45,
    borderRadius: 5,
    marginRight: 12,
  },
  eventMain: {
    flex: 1,
  },
  eventTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: C.navy,
  },
  schoolName: {
    fontSize: 12,
    color: C.secondaryText,
    marginTop: 5,
  },
  completedBadge: {
    fontSize: 10,
    color: '#13845F',
    backgroundColor: '#E5F7EF',
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 8,
    fontWeight: '700',
  },
  eventDetails: {
    marginTop: 14,
    gap: 7,
  },
  detailText: {
    fontSize: 12,
    color: C.secondaryText,
  },
  eventBottom: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
    paddingTop: 13,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  typeBadge: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  typeBadgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  completeButton: {
    backgroundColor: C.navy,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 9,
  },
  completeButtonText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  completedButton: {
    backgroundColor: '#E5F7EF',
  },
  completedButtonText: {
    color: '#13845F',
  },
  emptyCard: {
    backgroundColor: '#FFFFFF',
    padding: 25,
    borderRadius: 15,
    alignItems: 'center',
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: C.navy,
  },
  emptyText: {
    fontSize: 12,
    color: C.secondaryText,
    marginTop: 6,
  },
  noteCard: {
    backgroundColor: '#EAF2F8',
    padding: 16,
    borderRadius: 14,
    marginTop: 10,
  },
  noteTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: C.navy,
    marginBottom: 6,
  },
  noteText: {
    fontSize: 12,
    lineHeight: 19,
    color: C.secondaryText,
  },
  weekNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  weekNavButton: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  weekNavText: {
    fontSize: 20,
    color: C.navy,
    fontWeight: '700',
  },
  weekLabel: {
    fontSize: 14,
    fontWeight: '800',
    color: C.navy,
  },
  todayLink: {
    fontSize: 11,
    color: C.tealDark,
    fontWeight: '800',
    textAlign: 'center',
    marginTop: 2,
  },
  dayRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 20,
  },
  dayChip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 9,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: C.border,
  },
  dayChipActive: {
    backgroundColor: C.navy,
    borderColor: C.navy,
  },
  dayChipToday: {
    borderColor: C.teal,
  },
  dayName: {
    fontSize: 10,
    color: C.secondaryText,
    fontWeight: '700',
  },
  dayNumber: {
    fontSize: 16,
    color: C.navy,
    fontWeight: '800',
    marginTop: 2,
  },
  dayTextActive: {
    color: '#FFFFFF',
  },
  dayDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: C.teal,
    marginTop: 4,
  },
  dayDotEmpty: {
    backgroundColor: 'transparent',
  },
  section: {
    marginBottom: 22,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  secondaryButton: {
    backgroundColor: '#F1F4F8',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 9,
  },
  secondaryButtonText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.navy,
  },
  dangerButton: {
    backgroundColor: '#FFF0F0',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 9,
  },
  dangerButtonText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#C13F35',
  },
  disabled: {
    opacity: 0.5,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(10,25,45,0.55)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 22,
    maxHeight: '90%',
    width: '100%',
    maxWidth: 900,
    alignSelf: 'center',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  modalTitle: {
    color: C.navy,
    fontSize: 20,
    fontWeight: '800',
  },
  closeText: {
    color: C.secondaryText,
    fontSize: 28,
  },
  inputLabel: {
    color: C.navy,
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 7,
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 11,
    paddingHorizontal: 13,
    paddingVertical: 12,
    color: C.text,
    backgroundColor: '#FAFBFD',
    fontSize: 13,
  },
  row: {
    flexDirection: 'row',
    gap: 10,
  },
  saveButton: {
    backgroundColor: C.tealDark,
    padding: 15,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 12,
    minHeight: 48,
  },
  saveButtonText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 14,
  },
});
