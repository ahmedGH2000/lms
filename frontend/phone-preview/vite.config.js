import {defineConfig} from 'vite';
import vue from '@vitejs/plugin-vue';
import {resolve} from 'node:path';
export default defineConfig({plugins:[vue()],build:{outDir:'phone-build',emptyOutDir:true,assetsInlineLimit:1000000,cssCodeSplit:false,lib:{entry:resolve(process.cwd(),'phone-preview/main.js'),name:'NightjarPreview',formats:['iife'],fileName:()=> 'preview.js'},rollupOptions:{output:{inlineDynamicImports:true}}}});
