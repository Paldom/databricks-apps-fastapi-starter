import * as React from 'react'
import { Settings, User, Bell } from 'lucide-react'
import { useTranslation } from '@/i18n/client'
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
  const { theme, setTheme } = useUIStore()

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-medium">{t('settings.general.title')}</h3>
      <Separator />

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>{t('settings.general.theme')}</Label>
          <p className="text-sm text-muted-foreground">
            {t('settings.general.themeDescription')}
          </p>
        </div>
        <Select
          value={theme}
          onValueChange={(v) => setTheme(v as 'light' | 'dark')}
        >
          <SelectTrigger className="w-[140px]">
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
          <Label>{t('settings.general.language')}</Label>
          <p className="text-sm text-muted-foreground">
            {t('settings.general.languageDescription')}
          </p>
        </div>
        <LanguageSwitcher />
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

  const [formValues, setFormValues] = React.useState(serverValues)
  const [errors, setErrors] = React.useState<{
    name?: string
    email?: string
  }>({})
  const [showSuccess, setShowSuccess] = React.useState(false)

  // Re-sync form when server data changes
  React.useEffect(() => {
    setFormValues(serverValues)
  }, [serverValues])

  const isDirty =
    formValues.name !== serverValues.name ||
    formValues.email !== serverValues.email

  const validate = (): boolean => {
    const newErrors: typeof errors = {}
    if (!formValues.name.trim()) {
      newErrors.name = t('settings.profile.nameRequired')
    }
    if (
      !formValues.email.trim() ||
      !formValues.email.includes('@') ||
      !formValues.email.split('@')[1]?.includes('.')
    ) {
      newErrors.email = t('settings.profile.emailInvalid')
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const updateMutation = useUpdateUserSettings({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getGetUserSettingsQueryKey(),
        })
        setShowSuccess(true)
        setTimeout(() => setShowSuccess(false), 3000)
      },
    },
  })

  const handleSave = () => {
    if (!validate()) return
    updateMutation.mutate({
      data: {
        name: formValues.name,
        email: formValues.email,
        notifications: settingsData?.data.notifications ?? true,
      },
    })
  }

  const handleCancel = () => {
    setFormValues(serverValues)
    setErrors({})
  }

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
    <div className="space-y-6">
      <h3 className="text-lg font-medium">{t('settings.profile.title')}</h3>
      <Separator />

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="settings-name">{t('settings.profile.name')}</Label>
          <Input
            id="settings-name"
            value={formValues.name}
            onChange={(e) =>
              setFormValues((v) => ({ ...v, name: e.target.value }))
            }
          />
          {errors.name && (
            <p className="text-sm text-destructive">{errors.name}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="settings-email">{t('settings.profile.email')}</Label>
          <Input
            id="settings-email"
            type="email"
            value={formValues.email}
            onChange={(e) =>
              setFormValues((v) => ({ ...v, email: e.target.value }))
            }
          />
          {errors.email && (
            <p className="text-sm text-destructive">{errors.email}</p>
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
        <Button
          onClick={handleSave}
          disabled={!isDirty || updateMutation.isPending}
        >
          {updateMutation.isPending
            ? t('common.loading')
            : t('settings.profile.save')}
        </Button>
        <Button
          variant="outline"
          onClick={handleCancel}
          disabled={!isDirty || updateMutation.isPending}
        >
          {t('settings.profile.cancel')}
        </Button>
      </div>
    </div>
  )
}

function NotificationsSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: settingsData, isLoading } = useGetUserSettings()

  const serverValue = settingsData?.data.notifications ?? true
  const [notifications, setNotifications] = React.useState(serverValue)

  React.useEffect(() => {
    setNotifications(serverValue)
  }, [serverValue])

  const updateMutation = useUpdateUserSettings({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getGetUserSettingsQueryKey(),
        })
      },
    },
  })

  const handleToggle = (checked: boolean) => {
    setNotifications(checked)
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

export function SettingsDialog() {
  const { t } = useTranslation()
  const { settingsDialogOpen, setSettingsDialogOpen } = useUIStore()
  const [activeSection, setActiveSection] =
    React.useState<SettingsSection>('general')

  // Reset to general when dialog opens
  React.useEffect(() => {
    if (settingsDialogOpen) {
      setActiveSection('general')
    }
  }, [settingsDialogOpen])

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
      </DialogContent>
    </Dialog>
  )
}
