// The credits shown on the last landing slide. ONE small file to edit. The team to CONFIRM before the thesis defence: the names and their spelling, the adviser's title, the LGU offices that are named, and whether each
// data / tool credit is worded the way its owner wants. Nothing here says that anyone endorses or approves the project.
export const PROJECT_CREDITS = {
  developers: ['Ayzhiedy Jee D. Reyes', 'Cyrus Austin G. Andal', 'Charles Joseph “JC” S. Peralta', 'Angelo Genesis N. Talastas'],
  adviser: 'Dr. Nila D. Santiago',
  school: 'Technological Institute of the Philippines, Quezon City',
  course: 'CS 307 Thesis 1',
  lgu: { place: 'LGU San Mateo, Rizal', offices: ['MENRO', 'MPDC'] },
  // [name, what it is used for, licence or note as the project states it]
  data: [
    ['Esri World Imagery', 'the satellite map', 'Esri and its data providers'],
    ['OpenStreetMap', 'place search results when the optional geocoder is on', '© OpenStreetMap contributors'],
    ['SoilGrids (ISRIC)', 'the soil pH estimate (display only)', 'CC BY 4.0 [licence to be confirmed]'],
    ['Project species dataset', 'species data and pH ranges, with the references it lists', 'the project’s own dataset'],
  ],
  tools: [['React Bits', 'animation components adapted by the project (David Haz)', 'MIT with Commons Clause']],
}
