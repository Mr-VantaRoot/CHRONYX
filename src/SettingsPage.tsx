import {useEffect, useState} from 'react';
import {Download} from 'lucide-react';
import {loadReminderSettings, saveReminderSettings} from './event-store.js';
export function SettingsPage({
  theme,
  setTheme,
  profilePicture,
  setProfilePicture,
  setNotice,
  exportData,
  importJSON
}: any) {
  const [prefs, setPrefs] = useState<any>({
      '7d': true,
      '3d': true,
      '1d': true,
      '1h': true,
      customHours: 0
    }),
    [pictureError, setPictureError] = useState('');
  useEffect(() => {
    loadReminderSettings().then(result => {
      setPrefs((old: any) => ({
        ...old,
        ...result.settings
      }));
      if (result.offline) setNotice('Service unavailable. Reminder preferences are saved on this device and will sync when the service returns.');
    }).catch(error => setNotice(error instanceof Error ? error.message : 'Could not load reminder preferences.'));
  }, []);
  async function update(key: string, value: any) {
    const next = {
      ...prefs,
      [key]: value
    };
    setPrefs(next);
    try {
      const result = await saveReminderSettings(next);
      setPrefs((old: any) => ({
        ...old,
        ...result.settings
      }));
      setNotice(result.offline ? 'Service unavailable. Reminder preferences are queued locally and will sync when the service returns.' : '');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not save reminder preferences.');
    }
  }
  function changePicture(file?: File) {
    if (!file) return;
    setPictureError('');
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
      setPictureError('Choose a JPEG, PNG, WebP, or GIF image.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setPictureError('Choose an image smaller than 10 MB.');
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => setPictureError('Could not read that image.');
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => setPictureError('That image could not be opened.');
      image.onload = () => {
        if (!image.width || !image.height || image.width * image.height > 20000000) {
          setPictureError('Choose an image with 20 megapixels or fewer.');
          return;
        }
        const scale = Math.min(1, 512 / Math.max(image.width, image.height)),
          canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          setPictureError('Image processing is unavailable.');
          return;
        }
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        const value = canvas.toDataURL('image/jpeg', .82);
        try {
          localStorage.setItem('vantaProfilePicture', value);
          setProfilePicture(value);
        } catch {
          setPictureError('Could not save the image. Try a smaller picture.');
        }
      };
      image.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  }
  function removePicture() {
    try {
      localStorage.removeItem('vantaProfilePicture');
      setProfilePicture('');
      setPictureError('');
    } catch {
      setPictureError('Could not remove the saved picture from local storage.');
    }
  }
  return <><div className="page-heading"><div><div className="eyebrow">PREFERENCES</div><h1>Settings</h1><p>Make VANTA work the way you do.</p></div></div><div className="settings-wrap"><section className="settings-card"><h3>Profile picture</h3><p>Shown in your workspace sidebar. Stored privately on this device.</p><div className="profile-settings"><div className="avatar profile-preview">{profilePicture ? <img src={profilePicture} alt="Your profile" /> : 'V'}</div><div className="profile-picture-actions"><label className="outline-button file-button">Choose picture<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={e => {
                changePicture(e.target.files?.[0]);
                e.currentTarget.value = '';
              }} /></label>{profilePicture && <button className="text-button" onClick={removePicture}>Remove picture</button>}</div></div>{pictureError && <small className="form-error">{pictureError}</small>}<small>JPEG, PNG, WebP, or GIF · max 10 MB. Images are resized before saving.</small></section><section className="settings-card"><h3>Appearance</h3><p>Choose the interface theme that feels right.</p><div className="theme-choice"><button className={theme === 'dark' ? 'chosen' : ''} onClick={() => setTheme('dark')}>◐ &nbsp; Dark</button><button className={theme === 'light' ? 'chosen' : ''} onClick={() => setTheme('light')}>☼ &nbsp; Light</button></div></section><section className="settings-card"><h3>Data & backup</h3><p>Your competition data stays on this device.</p><div className="settings-actions"><button className="outline-button" onClick={() => exportData('json')}><Download size={15} /> Backup JSON</button><button className="outline-button" onClick={() => exportData('csv')}><Download size={15} /> Export CSV</button><label className="outline-button file-button">Import JSON<input type="file" accept="application/json,.json" onChange={e => {
              const file = e.target.files?.[0];
              if (file) importJSON(file);
              e.currentTarget.value = '';
            }} /></label></div></section><section className="settings-card"><h3>Reminders</h3><p>Choose when VANTA notifies you about starts and registration deadlines.</p><div className="reminder-options">{[['7d', '7 days before'], ['3d', '3 days before'], ['1d', '1 day before'], ['1h', '1 hour before']].map(([k, x]) => <label key={k}><input type="checkbox" checked={!!prefs[k]} onChange={e => update(k, e.target.checked)} /> {x}</label>)}</div><label className="custom-reminder">Custom reminder (hours before)<input type="number" min="0" max="8760" value={prefs.customHours || 0} onChange={e => update('customHours', Math.min(8760, Math.max(0, Number(e.target.value))))} /></label><small>Desktop reminders appear while VANTA is running in the background.</small></section><section className="settings-card"><h3>About VANTA</h3><p>Competition tracking, kept local and private.</p><span className="version-chip">VANTA · VERSION 1.0.0</span></section></div></>;
}
