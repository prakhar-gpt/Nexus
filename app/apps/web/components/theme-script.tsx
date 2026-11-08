export function ThemeScript() {
  const code = `(function() {
    try {
      var stored = localStorage.getItem('nexus_theme');
      if (stored === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    } catch (e) {}
  })()`;

  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}

