import {mkdir,copyFile,readFile} from 'node:fs/promises';
import {Script} from 'node:vm';
new Script(await readFile(new URL('app.js',import.meta.url),'utf8'));
await mkdir(new URL('dist/',import.meta.url),{recursive:true});
for(const file of ['index.html','style.css','app.js'])await copyFile(new URL(file,import.meta.url),new URL(`dist/${file}`,import.meta.url));
console.log('Dashboard syntax checked and static build created.');
