import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
  site: 'https://nsozturk.github.io',
  base: '/claude-code-local',
  integrations: [
    starlight({
      title: 'Claude Code Local',
      description: 'Run Claude Code on your own local models at zero API cost with instant VRAM eviction and unified memory management.',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/nsozturk/claude-code-local' },
      ],
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Introduction', slug: 'index' },
            { label: 'Installation', slug: 'getting-started/installation' },
            { label: 'Quick Start', slug: 'getting-started/quickstart' },
          ],
        },
        {
          label: 'Architecture & Engineering',
          items: [
            { label: 'System Topology', slug: 'architecture/overview' },
            { label: 'Dynamic Memory & VRAM Eviction', slug: 'architecture/memory-management' },
          ],
        },
        {
          label: 'Models & Optimization',
          items: [
            { label: 'Importing Models', slug: 'models/importing' },
            { label: 'Recommended Models', slug: 'models/recommended' },
          ],
        },
        {
          label: 'CLI & Controls',
          items: [
            { label: 'Commands & Flags', slug: 'cli/commands' },
          ],
        },
      ],
    }),
  ],
});
