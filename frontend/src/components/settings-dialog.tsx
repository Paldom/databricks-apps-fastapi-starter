import * as React from 'react'
import { Settings, User, Bell } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useUIStore } from '@/shared/store/ui'
import { cn } from '@/lib/utils'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LanguageSwitcher } from '@/components/language-switcher'
import {
  useGetUserSettings,
  useUpdateUserSettings,
  getGetUserSettingsQueryKey,
} from '@/shared/api/generated/settings/settings'
import { useQueryClient } from '@tanstack/react-query'

type SettingsSection = 'general' | 'profile' | 'notifications'

const NAV_ITEMS = [
  { id: 'general', icon: Settings, labelKey: 'settings.nav.general' },
  { id: 'profile', icon: User, labelKey: 'settings.nav.profile' },
  { id: 'notifications', icon: Bell, labelKey: 'settings.nav.notifications' },
] as const

function GeneralSection() {
  const { t } = useTranslation()
  const theme = useUIStore((s) => s.theme)
  const setTheme = useUIStore((s) => s.setTheme)

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-medium">{t('settings.general.title')}</h3>
      <Separator />

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="settings-theme">{t('settings.general.theme')}</Label>
          <p className="text-sm text-muted-foreground">
            {t('settings.general.themeDescription')}
          </p>
        </div>
        <Select
          value={theme}
          onValueChange={(v) => setTheme(v as 'light' | 'dark')}
        >
          <SelectTrigger id="settings-theme" className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="light">{t('settings.general.light')}</SelectItem>
            <SelectItem value="dark">{t('settings.general.dark')}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Separator />

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label id="settings-language-label">
            {t('settings.general.language')}
          </Label>
          <p className="text-sm text-muted-foreground">
            {t('settings.general.languageDescription')}
          </p>
        </div>
        <LanguageSwitcher labelledById="settings-language-label" />
      </div>
    </div>
  )
}

function ProfileSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: settingsData, isLoading } = useGetUserSettings()

  const serverValues = React.useMemo(
    () => ({
      name: settingsData?.data.name ?? '',
      email: settingsData?.data.email ?? '',
    }),
    [settingsData]
  )

  // Built per-render (memoized on t) so messages follow the current language.
  // zod 4: z.email() is the top-level API; z.string().email() is deprecated.
  const profileSchema = React.useMemo(
    () =>
      z.object({
        name: z.string().min(1, t('settings.profile.nameRequired')),
        email: z.email(t('settings.profile.emailInvalid')),
      }),
    [t]
  )

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(profileSchema),
    // `values` re-syncs (resets) the form whenever server data changes,
    // replacing the previous setState-in-effect pattern.
    values: serverValues,
  })

  const [showSuccess, setShowSuccess] = React.useState(false)
  const successTimeoutRef =
    React.useRef<ReturnType<typeof setTimeout>>(undefined)

  // Clear any pending success timeout on unmount
  React.useEffect(() => () => clearTimeout(successTimeoutRef.current), [])

  const updateMutation = useUpdateUserSettings({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getGetUserSettingsQueryKey(),
        })
        setShowSuccess(true)
        clearTimeout(successTimeoutRef.current)
        successTimeoutRef.current = setTimeout(
          () => setShowSuccess(false),
          3000
        )
      },
    },
  })

  const onSubmit = handleSubmit((values) => {
    updateMutation.mutate({
      data: {
        name: values.name,
        email: values.email,
        notifications: settingsData?.data.notifications ?? true,
      },
    })
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-7 w-20" />
        <Separator />
        <div className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      </div>
    )
  }

  return (
    <form className="space-y-6" onSubmit={(e) => void onSubmit(e)} noValidate>
      <h3 className="text-lg font-medium">{t('settings.profile.title')}</h3>
      <Separator />

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="settings-name">{t('settings.profile.name')}</Label>
          <Input
            id="settings-name"
            aria-invalid={errors.name ? true : undefined}
            aria-describedby={errors.name ? 'settings-name-error' : undefined}
            {...register('name')}
          />
          {errors.name && (
            <p id="settings-name-error" className="text-sm text-destructive">
              {errors.name.message}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="settings-email">{t('settings.profile.email')}</Label>
          <Input
            id="settings-email"
            type="email"
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={errors.email ? 'settings-email-error' : undefined}
            {...register('email')}
          />
          {errors.email && (
            <p id="settings-email-error" className="text-sm text-destructive">
              {errors.email.message}
            </p>
          )}
        </div>
      </div>

      {updateMutation.isError && (
        <p className="text-sm text-destructive">
          {t('settings.profile.saveError')}
        </p>
      )}
      {showSuccess && (
        <p className="text-sm text-green-600">
          {t('settings.profile.saveSuccess')}
        </p>
      )}

      <div className="flex gap-2">
        <Button type="submit" disabled={!isDirty || updateMutation.isPending}>
          {updateMutation.isPending
            ? t('common.loading')
            : t('settings.profile.save')}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => reset()}
          disabled={!isDirty || updateMutation.isPending}
        >
          {t('settings.profile.cancel')}
        </Button>
      </div>
    </form>
  )
}

function NotificationsSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: settingsData, isLoading } = useGetUserSettings()

  const updateMutation = useUpdateUserSettings({
    mutation: {
      // Returning the promise keeps the mutation pending until the refetch
      // completes, so the optimistic value below never flickers back.
      onSuccess: () =>
        queryClient.invalidateQueries({
          queryKey: getGetUserSettingsQueryKey(),
        }),
    },
  })

  const serverValue = settingsData?.data.notifications ?? true
  // Derived optimistic state: while saving, show the value being saved.
  const notifications = updateMutation.isPending
    ? (updateMutation.variables?.data.notifications ?? serverValue)
    : serverValue

  const handleToggle = (checked: boolean) => {
    updateMutation.mutate({
      data: {
        name: settingsData?.data.name ?? '',
        email: settingsData?.data.email ?? '',
        notifications: checked,
      },
    })
  }

  if (isLoading) {
    return <Skeleton className="h-20 w-full" />
  }

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-medium">
        {t('settings.notifications.title')}
      </h3>
      <Separator />

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="settings-notifications">
            {t('settings.notifications.enable')}
          </Label>
          <p className="text-sm text-muted-foreground">
            {t('settings.notifications.enableDescription')}
          </p>
        </div>
        <Switch
          id="settings-notifications"
          checked={notifications}
          onCheckedChange={handleToggle}
          disabled={updateMutation.isPending}
        />
      </div>
    </div>
  )
}

// Lives inside DialogContent, which Radix unmounts on close, so the active
// section naturally resets to 'general' every time the dialog opens.
function SettingsBody() {
  const { t } = useTranslation()
  const [activeSection, setActiveSection] =
    React.useState<SettingsSection>('general')

  return (
    <div className="flex h-[480px]">
      {/* Left nav */}
      <nav className="flex w-[200px] shrink-0 flex-col gap-1 border-r bg-muted/40 p-4">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveSection(item.id)}
            className={cn(
              'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors text-left',
              activeSection === item.id
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
            )}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {t(item.labelKey)}
          </button>
        ))}
      </nav>

      {/* Right content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeSection === 'general' && <GeneralSection />}
        {activeSection === 'profile' && <ProfileSection />}
        {activeSection === 'notifications' && <NotificationsSection />}
      </div>
    </div>
  )
}

export function SettingsDialog() {
  const { t } = useTranslation()
  const settingsDialogOpen = useUIStore((s) => s.settingsDialogOpen)
  const setSettingsDialogOpen = useUIStore((s) => s.setSettingsDialogOpen)

  // Keyboard shortcut: Ctrl/Cmd + ,
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === ',' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setSettingsDialogOpen(!settingsDialogOpen)
      }
    }
    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [settingsDialogOpen, setSettingsDialogOpen])

  return (
    <Dialog open={settingsDialogOpen} onOpenChange={setSettingsDialogOpen}>
      <DialogContent className="sm:max-w-3xl p-0 gap-0 overflow-hidden">
        <DialogTitle className="sr-only">{t('settings.title')}</DialogTitle>
        <SettingsBody />
      </DialogContent>
    </Dialog>
  )
}
