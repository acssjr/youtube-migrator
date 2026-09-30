import {test} from 'node:test';
import assert from 'node:assert/strict';
import {composeStructure,initialVideoStructure,baseStructure,instagramUrl} from '../src/services/descriptionStructure.mjs';
test('complete structure without a music reference, main then guest and correct archive',()=>{
 const common={...baseStructure(),mainInstagram:'@principal',playlists:'🎺 Projeto Retreta\n\n1️⃣ https://www.youtube.com/playlist?list=abc'};
 const guest={...initialVideoStructure({ensemble:'Sociedade Filarmônica União Sanfelixta'}),instagram:'convidada',history:'Sobre a instituição: TEXTO EXATO.'};
 const text=composeStructure(common,guest);
 assert.ok(text.startsWith('Siga a Sociedade Filarmônica 25 de Março'));
 assert.ok(text.indexOf('/principal/')<text.indexOf('/convidada/'));
 assert.ok(text.includes('Esta partitura pertence ao acervo da Sociedade Filarmônica União Sanfelixta.'));
 assert.ok(text.includes(guest.history));assert.ok(text.endsWith(common.playlists));
 assert.ok(!text.includes('Sobre o compositor'));
});
test('preserves exact approved paragraphs and other social links when changing instagram',()=>{
 const body='Sobre o compositor: Tertuliano Santos — TEXTO EXATO.\nLinha seguinte.';
 const common={...baseStructure(),mainInstagram:'novo',mainFollow:'Siga a Filarmônica 25 de Março nas suas redes sociais:\nInstagram: https://www.instagram.com/antigo/\nFacebook: https://facebook.com/exemplo'};
 const text=composeStructure(common,{...initialVideoStructure({body}),includeArchive:false});
 assert.ok(text.includes(body));assert.ok(text.includes('https://facebook.com/exemplo'));assert.ok(text.includes('/novo/'));assert.ok(!text.includes('/antigo/'));
});
test('no duplicate guest block for the main ensemble and editable ownership',()=>{
 const video=initialVideoStructure({ensemble:'Sociedade Filarmônica 25 de Março'});assert.equal(video.guest,false);
 video.archive='Acervo de outra instituição';assert.ok(composeStructure(baseStructure(),video).includes('acervo da Acervo de outra instituição.'));
});
test('rejects non Instagram urls and invalid ownership',()=>{
 assert.throws(()=>instagramUrl('https://evil.example/x'));
 assert.throws(()=>instagramUrl('@a b'));
 assert.throws(()=>composeStructure(baseStructure(),{...initialVideoStructure(),includeArchive:true}));
});

test('emoji follow call adjusts the chosen name and preserves other networks',()=>{
 const common={...baseStructure(),mainName:'Filarmônica Outra',mainInstagram:'@outra',mainFollow:'👉🏻 Siga a Filarmônica 25 de Março no Instagram e acompanhe as novidades:\nhttps://instagram.com/filarmonica25demarco\nFacebook: https://facebook.com/25demarco'};
 const text=composeStructure(common,{...initialVideoStructure(),includeArchive:false});
 assert.ok(text.startsWith('👉🏻 Siga a Filarmônica Outra no Instagram e acompanhe as novidades:'));
 assert.ok(text.includes('https://www.instagram.com/outra/'));assert.ok(text.includes('Facebook: https://facebook.com/25demarco'));
});
