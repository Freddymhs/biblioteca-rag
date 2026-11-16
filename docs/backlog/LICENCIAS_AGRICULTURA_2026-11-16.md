# Licencias del corpus `agricultura`: tabla para el veredicto de Freddy (tarea 4.6)

Armada el 2026-11-16 por una sesión asistida por IA. **Nada de esto es un veredicto**: hasta que Freddy marque una
licencia como verificada (`PUT /api/espacios/laboral/colecciones/agricultura/documentos/{id}/licencia` con
`"verificada": true`), todo documento queda con `licencia_verificada = false` y por lo tanto **no es público**, aunque
la colección lo sea.

## Cómo se leyó

- Corpus en solo lectura: `/home/fmarcosdev/Volumes/Extended/github/PRODUCTION/BIBLIOTECAPARARAG-AGRICULTURA/`.
- **Documentos leídos: 89 de 89** (los 3 archivos de control no cuentan). De cada PDF, con `pdftotext`, primero las
  4 primeras páginas y las 2 últimas, donde va la página legal; si ahí no había nada, **el documento entero** (columna
  «Páginas leídas»). El `.txt`, completo. Todos dieron texto.
- Se buscó: Creative Commons (texto y URL), «todos los derechos reservados» / «prohibida la reproducción», «permitida
  su reproducción citando la fuente», la nota de la FAO sobre uso no comercial, dominio público, acceso abierto y `©`.
- La columna **Propuesta** sale de reglas fijas aplicadas a esa evidencia, en este orden: Creative Commons → FAO no
  comercial → reproducción citando la fuente → derechos reservados → solo `©` → nada. «Sin declaración en todo el
  documento» no quiere decir que sea libre: sin licencia declarada, rige el derecho de autor del país de origen.
- La **Fuente** viene de `catalogo.json`.

## Resumen de la propuesta

- 51: Sin declaración de licencia en todo el documento
- 10: Todos los derechos reservados / prohibida la reproducción sin autorización
- 10: Reproducción permitida citando la fuente (no CC)
- 7: Copyright sin licencia visible en las páginas leídas
- 4: CC BY 4.0
- 2: CC BY-NC-SA 4.0
- 1: CC BY-NC 3.0
- 1: FAO: uso no comercial autorizado citando la fuente (no CC)
- 1: CC BY
- 1: CC BY 3.0
- 1: CC (variante no legible)

## Preguntas para Freddy

1. ¿Una «reproducción permitida citando la fuente» (los boletines INIA Chile) alcanza para publicar fragmentos con
   cita?
2. Los «todos los derechos reservados» (INIA Perú, FAO-24, algunas revistas): ¿quedan fuera, o se pide permiso a la
   fuente?
3. ¿Las licencias no comerciales (CC BY-NC-SA, FAO) calzan con un servicio gratuito sin fines de lucro?
4. Los 51 sin ninguna declaración (leídos enteros): ¿quedan privados, o se le pide permiso a cada fuente?

## Tabla

| # | Archivo | Fuente (catálogo) | Páginas leídas | Evidencia | Propuesta | Veredicto |
|---|---|---|---|---|---|---|
| 1 | 10. Compatibilidad del injerto por yemas en cinco variedades de cítricos utilizando patrones resistentes en la zona de Babahoyo.pdf | Magazine de las Ciencias (CICAG) — Univ. Técnica de Babahoyo | completo (p1-17) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 2 | 13197_2010_Article_85.pdf | Journal of Food Science and Technology | completo (p1-6) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 3 | 1453309498_Volume 3 Issue 1.pdf | International Journal of Innovations in Engineering Research and Technology | completo (p1-12) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 4 | 1_IF PGR Región Arica y Parinacota.pdf | CNR (Comisión Nacional de Riego) — Ministerio de Agricultura Chile — elaborado por ARRAU | completo (p1-382) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 5 | 3062-Texto del artículo-10746-1-10-20200826.pdf | Universidad Nacional del Santa (Perú) | p1-4, p14-15 | p1-4: «© 2020 All rights reserved E-mail: luzpaucar@uns.edu.pe (L.M. Paucar-Menacho). DOI: 1» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 6 | 55-66.pdf | Enfoque UTE | p1-4, p11-12 | p1-4: «CC BY 4.0 Estudio multiespectral del cultivo de tuna para determinar los índices NDVI 1, CWSI2» | CC BY 4.0 | sin verificar |
| 7 | 58-72-8688-Toaquiza 3.pdf | Universidad & Ciencia — Univ. de Ciego de Ávila / Univ. Técnica de Cotopaxi | p1-4, p15-16 | p15-16: «Ciego de Ávila, Cuba Esta obra está bajo una licencia internacional Creative Commons Atribución-NoComercial-CompartirIgual 4.0. Se permite s» | CC BY-NC-SA 4.0 | sin verificar |
| 8 | 6500+Pdf+(1).pdf | UABC / TecNM Instituto Tecnológico de Conkal | completo (p1-15) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 9 | 978-607-59951-2-0.pdf | Editorial Tercer Sol / Univ. Nacional Agraria La Molina | completo (p1-91) | documento completo: «(Peer Review Double Blinded). Esta publicación cuenta con licencia Creative Commons Reconocimiento - NoComercial - SinObraDerivada 3.0 Unpor» | CC BY-NC 3.0 | sin verificar |
| 10 | A review on dragon fruit .pdf | Journal of Research and Reviews in Yoga & Ayurvedic Sciences | p1-4, p8-9 | p1-4: «flesh and pink skin of Hylocereus HBRP Publication Page 21-29 2024. All Rights Reserved Page 21» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 11 | Agenda Regional de Innovación Agraria Tacna 2021-2025.pdf | CTRIA Tacna / MIDAGRI Perú | completo (p1-24) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 12 | Belaraibi_43-49_MJAS Vol 7_(1)_march_2026.pdf | Moroccan Journal of Agricultural Sciences (École Nationale d'Agriculture de Meknès) | p1-4, p6-7 | p1-4: «k et al., 2022). and Flint, 2018), while indirect damage concerns the © Moroccan Journal of Agricultural Sciences • e-ISSN: 2550-553X» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 13 | Boletín INIA N° 149.pdf | INIA Chile | p1-4, p170-171 | p1-4: «Chile. ISSN 071 7 - 4829 Permitida su reproducción total o parcia l citando la fuente y el autor. Diseño y Diagramación : Jorge Berríos Vi l» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 14 | Boletín INIA N° 259 | INIA Chile — Quilamapu | p1-4, p88-89 | p1-4: «Ministerio de Agricultura. Permitido su reproducción total o parcial citando la fuente y editores. Cita bibliográfica correcta : Maldonado l» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 15 | Boletín INIA N° 302.pdf | INIA Chile | p1-4, p102-103 | p1-4: «313676. ISSN 0717 - 4829. Permitida su reproducción total o parcial citando la fuente y los a utores. Diseño y D iag ramac ión: Jorg e Berrí» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 16 | Boletín INIA N° 355 | INIA Chile — INIA Intihuasi | p1-4, p60-61 | p1-4: «. ISSN 0717-4829 Autorizada su reproducción total o parcial citando la fuente y los autores Diseño y Diagramación: Jorge Berríos V., Diseñad» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 17 | Boletín INIA N° 384 | INIA Chile — INIA Ururi / CONADI | p1-4, p87-88 | p1-4: «6. ISSN 0717 - 4829 Permitida su reproducción total o parcial citando la fuente y/o autores. Diseño y diagramación: Jorge Berrios V., Diseña» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 18 | CNR-boletin-Kc-cultivos.pdf | Comisión Nacional de Riego (CNR), Chile | completo (p1-7) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 19 | Capitulo 4.pdf | INIA Chile (Boletín INIA N° 355) | completo (p1-8) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 20 | Cultivo de la Tuna y Crianza de la Cochinilla - INIA Tacna.pdf | INIA Perú | p1-4, p31-32 | p1-4: «, 1997 Tiraje: 1 000 ejemplares Abril, 2002 Tiraje: 300 ejemplares Prohibida la reproducción total o parcial sin autorización Conservación d» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 21 | EMBRAPA-pitahaya-gaia-scientia.pdf | Gaia Scientia (UFPB) — autores de UFPB, UEPB y Embrapa Agroindústria Tropical | completo (p1-9) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 22 | FAO-24-crop-water-requirements.pdf | FAO | p1-4, p155-156 | p1-4: «M-56 ISBN 92-5-100279-7 All rights reserved. No part of this publication may be reproduced, stored in a retrieval system, or transmit» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 23 | FAO-56-crop-evapotranspiration-Kc.pdf | FAO | completo (p1-333) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 24 | FAO-Ch16-Fertigation.pdf | FAO | completo (p1-5) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 25 | FAO-Ch5-Sources-plant-nutrients.pdf | FAO (Fertilizer and Plant Nutrition Bulletin 16) | completo (p1-144) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 26 | FAO-Ch8-Nutrient-management.pdf | FAO (Fertilizer and Plant Nutrition Bulletin 16) | completo (p1-115) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 27 | FAO-Fertilizer-Plant-Nutrition-Bulletin16.pdf | FAO | p1-4, p58-59 | p1-4: «e delimitation of its frontiers or boundaries. ISBN 92-5-105490-8 All rights reserved. Reproduction and dissemination of material in this in» | FAO: uso no comercial autorizado citando la fuente (no CC) | sin verificar |
| 28 | FAO-Fruit-trees-vines-Fereres.pdf | FAO (Irrigation and Drainage Paper, editor E. Fereres) | completo (p1-189) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 29 | FAO-Olive-growing-Nepal.pdf | FAO / Department of Agriculture Nepal (TCP/NEP/6713) | completo (p1-70) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 30 | FAO-Strategies-olive-groves-steep.pdf | ICARDA / FAO | completo (p1-25) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 31 | FAO-Yield-response-water-frutales.pdf | FAO (Fereres, Goldhamer, Sadras et al.) | completo (p1-51) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 32 | Ficha Técnica INIA Intihuasi N° 138 - Lúcumo chileno.pdf | INIA Chile — Intihuasi | completo (p1-2) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 33 | Fortalecimiento de capacidades técnico-productivas de los productores de maracuyá en los distritos de Barranca, Chimbote y Olmos_207_PI. Resultados..pdf | INIA Perú (DDTA / PNIA) | completo (p1-58) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 34 | Gomez-2024-AquaCrop-frijol-requerimientos-hidricos.pdf | Agrisost (Universidad de Granma, Cuba) | completo (p1-8) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 35 | Granada Pomegranate - Saline Irrigation Morphometric Tolerance 2019.pdf | Revista Brasileira de Engenharia Agrícola e Ambiental | completo (p1-6) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 36 | Guía Técnica del Cultivo de Olivo en la Región Tacna.pdf | INIA Perú | p1-4, p90-91 | p1-4: «el Depósito Legal en la Biblioteca Nacional del Perú N° 2022-02517 Prohibida la reproducción de este libro por cualquier medio, total o parc» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 37 | Guía Técnica del cultivo de pitahaya (Hylocereus megalanthus) en la región Amazonas.pdf | INIA Perú — Estación Experimental Agraria Amazonas | p1-4, p20-21 | p1-4: «ho el Depósito Legal en la Biblioteca Nacional del Perú N° 2020-00447 Prohibida la reproducción de este libro por cualquier medio, total o p» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 38 | Hussain 2021_Ch11_Integrated Weed Management.pdf | Springer Nature (Hussain et al.; ed. E. Lichtfouse) | p1-4, p26-27 | p1-4: «mmercialization (ORIC), University of Gujrat (UOG), Gujrat, Pakistan © The Editor(s) (if applicable) and The Author(s), under exclusive lice» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 39 | Informativo INIA N° 91 | INIA Chile — CIE Agricultura del Desierto y Altiplano, INIA Ururi | completo (p1-4) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 40 | IrrigationScience-2024-Kc-subtropical-tropical-orchards.pdf | Irrigation Science (Springer; Paredes, Petry, Oliveira, Montoya, López-Urrea, Pereira) | p1-4, p38-39 | p1-4: «Luis S. Pereira1 Received: 29 January 2024 / Accepted: 4 March 2024 © The Author(s) 2024 Abstract This paper provides an overview of the res» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 41 | Libro INIA N° 35.pdf | INIA Chile | completo (p1-110) | documento completo: « Sin O  Sin G  Sin Z s  Cos O  Cos G  Sin hs @ ©S ¹ (9) Donde ISC» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 42 | MANUAL DE COSECHA Y POSCOSECHA DE PITAHAYA AMARILLA (Hylocereus megalanthus).pdf | INIA Perú | p1-4, p61-62 | p1-4: «Depósito Legal en la Biblioteca Nacional del Perú N° 2021-08037. Prohibida la reproducción de esta guía por cualquier medio, total o parcial» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 43 | Mamamani_et-al_2024_descriptores_tuna.pdf | INIA Perú | p1-4, p32-33 | p1-4: «Susceptibilidad a plagas y Todos los derechos reservados. 4.6.» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 44 | Manejo cultivo integrado maracuya.txt | INIA Perú — Dirección de Recursos Genéticos y Biotecnología | completo | — | Sin declaración de licencia en todo el documento | sin verificar |
| 45 | NR32257.pdf | INIA Chile — Quilamapu / Raihuen | p1-4, p143-144 | p1-4: «Ministerio de Agricultura. Permitida su reproducción total o parcial citando la fuente y editores. Cita bibliográfica correcta: Lavín A., Ar» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 46 | NR32267.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-23) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 47 | NR32268.pdf | INIA Chile (Boletín INIA N° 120) | p1-4, p17-18 | p17-18: «lifornia. Division of Agricultura/ Sciences University of California. Copyright. 189 p. Fruta/es: especies con porenc1a! en el secano mtenor» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 48 | NR32269.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-29) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 49 | NR32270.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-14) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 50 | NR32271.pdf | INIA Chile (Boletín INIA N° 120) | p1-4, p9-10 | p9-10: «lifornia. Division of Agricultura/ Sciences University of California. Copyright. 189 p. Frutales: especies con porenOJa/ en el secano interi» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 51 | NR32272.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-11) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 52 | NR32273.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-8) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 53 | NR32274.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-15) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 54 | NR32275.pdf | INIA Chile (Boletín INIA N° 120) | completo (p1-9) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 55 | NR38625.pdf | INIA Chile — INIA Ururi | p1-4 | p1-4: «. Permitida la reproducción del contenido de esta publicación, citando la fuente y el autor INIA-URURI, Magallanes 1865, Arica, Región de Ar» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 56 | NR39750.pdf | INIA Chile — INIA Ururi | p1-4, p91-92 | p1-4: «ISSN 0717 – 4829. Permitida su reproducción total o parcial citando la fuente y los autores. Corrección técnica: Patricio Hinrichsen R. Bioq» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 57 | NR39752.pdf | INIA Chile — INIA Ururi | completo (p1-9) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 58 | NR40212.pdf | INIA Chile — INIA Ururi | p1-4, p140-141 | p1-4: «313676. ISSN 0717 – 4829. Permitida su reproducción total o parcial citando la fuente y los autores. Corrección de textos: Marisol González » | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 59 | NR40213.pdf | INIA Chile — INIA Ururi (Boletín INIA N° 304) | completo (p1-50) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 60 | NR40214.pdf | INIA Chile — INIA Ururi (Boletín INIA N° 304) | completo (p1-17) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 61 | NR40215.pdf | INIA Chile — INIA Ururi (Boletín INIA N° 304) | completo (p1-24) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 62 | NR40216.pdf | INIA Chile — INIA Ururi (Boletín INIA N° 304) | completo (p1-19) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 63 | NR40217.pdf | INIA Chile — INIA Ururi (Boletín INIA N° 304) | completo (p1-19) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 64 | NR40238.pdf | INIA Chile — INIA Ururi | p1-4 | p1-4: «Permitida la reproducción del contenido de esta publicación, citando la fuente y el autor. INIA-URURI, Magallanes 1865, Arica, Región de Ari» | Reproducción permitida citando la fuente (no CC) | sin verificar |
| 65 | NR40748.pdf | INIA Chile (Boletín INIA N° 355) | completo (p1-14) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 66 | NR40749.pdf | INIA Chile (Boletín INIA N° 355) | completo (p1-5) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 67 | NR40750.pdf | INIA Chile (Boletín INIA N° 355) | completo (p1-16) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 68 | NR42668.pdf | INIA Chile — Programa GORE-INIA Araucanía Frutícola | p1-4, p51-52 | p1-4: «Gobierno Regional de La Araucanía en el contexto del Plan Impulso. Prohibida la reproducción parcial o total de este documento sin autorizac» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 69 | NR43004.pdf | INIA Chile — CORFO | p1-4, p65-66 | p1-4: «Temuco Esta obra está bajo una Licencia Creative Commons Atribución-NoComercial-CompartirIgual 4.0 Internacional. 4 BOLETÍN INIA N° 470» | CC BY-NC-SA 4.0 | sin verificar |
| 70 | Oxidative Medicine and Cellular Longevity - 2017 - del Socorro Santos Díaz - Opuntia spp   Characterization and Benefits in.pdf | Oxidative Medicine and Cellular Longevity | p1-4, p16-17 | p1-4: «ntos Díaz et al. This is an open access article distributed under the Creative Commons Attribution License, which permits unrestricted use, » | CC BY | sin verificar |
| 71 | Pitura-2013-fertilizacion-potasio-calcio-apio.pdf | Modern Phytomorphology (University of Life Sciences in Lublin, Polonia) | p1-4, p5-5 | p1-4: «, one 2 dm3 pot filled with transitional peat with © The Author(s), 2013 78» | Copyright sin licencia visible en las páginas leídas | sin verificar |
| 72 | UCANR-pitahaya-nutritional-description.pdf | UC South Coast Research and Extension Center (UC ANR), Dragon Fruit / Pitahaya Seminar | completo (p1-21) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 73 | UCANR-pitahaya-water-efficient.pdf | University of California Cooperative Extension / UC ANR (Lobo, Fernandez de Soto, Aguiar, Tanizaki) | completo (p1-3) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 74 | USDA-NRCS-NEH-ch2-crop-water-requirements.pdf | USDA Soil Conservation Service (NRCS) | completo (p1-302) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 75 | USDA-blueberry-irrigation-methods.pdf | HortScience (USDA-ARS y Oregon State University; Bryla, Gartung, Strik) | completo (p1-7) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 76 | Villagomez-Cultive_tunas_y_tendrá_buenos_ingresos.pdf | INIA Perú (Instituto Nacional de Investigación Agraria), Folleto R.I. Nº 10-00 | p1-4, p17-18 | p1-4: «, 2000 Tiraje: 700 ejemplares Prohibida la reproducción total o parcial 3 INTRODUCC» | Todos los derechos reservados / prohibida la reproducción sin autorización | sin verificar |
| 77 | Viticultura andina Valle de Codpa.pdf | RIVAR — Instituto de Estudios Avanzados, Universidad de Santiago de Chile | completo (p1-15) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 78 | Zenodo-Guayaba-hibridos.pdf | Alcances Tecnológicos (INTA Costa Rica y Universidad de Costa Rica; Bogantes y Mora) | completo (p1-8) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 79 | admin,+Editor_a+de+la+revista,+1081-1093+Art..pdf | INIFAP / Revista Mexicana de Ciencias Agrícolas | completo (p1-13) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 80 | agronomy-09-00787.pdf | Agronomy (MDPI) | p1-4, p11-12 | p11-12: «e Commons Attribution (CC BY) license (http://creativecommons.org/licenses/by/4.0/).» | CC BY 4.0 | sin verificar |
| 81 | agronomy-10-01065-v2.pdf | Agronomy (MDPI) | p1-4, p18-19 | p18-19: «Commons Attribution (CC BY) license (http://creativecommons.org/licenses/by/4.0/).» | CC BY 4.0 | sin verificar |
| 82 | arandano-Kc-evapotranspiracion-riego.pdf | InTech, capítulo en 'Evapotranspiration - From Measurements to Agricultural and Environmental Applications' (David R. Bryla, USDA-ARS) | p1-4, p21-22 | p21-22: «en. This is an open access article distributed under the terms of the Creative Commons Attribution 3.0 License, which permits unrestricted u» | CC BY 3.0 | sin verificar |
| 83 | foods-10-00434-v2.pdf | Foods (MDPI) — ICIA / CSIC | p1-4, p25-26 | p1-4: «lly from Mexico and they are interesting to Spanish conditions of the Creative Commons growers and farmers due to their physical chara» | CC (variante no legible) (probable: el texto de la licencia sale partido) | sin verificar |
| 84 | granada-fenologia.pdf | Termiz Institute of Agrotechnologies and Innovative Development (Uzbekistán); revista ISSN 2349-0012 | completo (p1-5) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 85 | subtropical-tropical-fruit-Kc-reference.pdf | UUHF (apuntes del Dr. Kulapati Hipparagi), India | completo (p1-176) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 86 | umestre,+Editor_a+de+secciÃ³n,+29-40_LaTÃ©cnicaE20-2018.pdf | Universidad Técnica de Manabí — La Técnica Revista de las Agrociencias | completo (p1-12) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 87 | uva-fenologia.pdf | Plants (MDPI); Universidad de Tuscia y CREA, Italia | p1-4, p17-18 | p17-18: «Commons Attribution (CC BY) license (http://creativecommons.org/licenses/by/4.0/).» | CC BY 4.0 | sin verificar |
| 88 | var_www_drupal_7.59_euraf_files_pub_kc_uploads_20190129_-_factsheet_08_-_web_-_it.pdf | EURAF / proyecto AFINET (Horizon 2020); autores Consalvo y Pisanelli, CNR-IRET | completo (p1-2) | — | Sin declaración de licencia en todo el documento | sin verificar |
| 89 | vol7n2p2.pdf | Latin-American Journal of Computing (LAJC), Vol. VII, Issue 2 (Telcombas S.A., Ecuador) | completo (p1-6) | — | Sin declaración de licencia en todo el documento | sin verificar |
