import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import { mintlify } from '@mintlify/astro';

export default defineConfig({
  site: 'https://zhouyaoji.github.io',
  base: '/northstar-docs-frameworks/mintlify',
  output: 'static',
  outDir: '../../public/mintlify',
  integrations: [mintlify({ docsDir: './docs' }), react(), mdx()],
});
