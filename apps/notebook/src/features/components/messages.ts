export const pl = {
  title: "Zapisz jako komponent",
  intro:
    "Wyprowadzenia z rysunku są pinami na obrysie. Przeciągnij pin w inne miejsce albo na inną stronę, a róg pudełka — żeby dać mu więcej miejsca.",
  name: "Nazwa",
  pins: "Piny",
  sides: { left: "z lewej", right: "z prawej", top: "u góry", bottom: "na dole" },
  dragHint: "przeciągaj piny i róg pudełka",
  keysHint: "Albo wybierz pin i przesuwaj go strzałkami — także na inną stronę.",
  size: "Rozmiar",
  fit: "Dopasuj do pinów",
  preview: "Komponent: przeciągaj piny po obrysie",
  save: "Zapisz komponent",
  replaceButton: "Zastąp komponent",
  willReplace: "Komponent o tej nazwie już jest — zapis go zastąpi.",
  saving: "Zapisuję…",
  saved:
    "Zapisano „{{name}}”. Znajdziesz go w bibliotece elementów (przycisk Elementy na schemacie), w sekcji Moje komponenty — na każdym schemacie, w każdej notatce.",
  done: "Gotowe",
  failed: "Nie udało się zapisać — spróbuj jeszcze raz.",
  replace: "Komponent „{{name}}” już jest. Zastąpić go tym?",
  noPorts:
    "Na tym rysunku nie ma wyprowadzeń. Postaw element Wyprowadzenie (biblioteka elementów → Połączenia) w każdym miejscu, którym komponent ma się łączyć z resztą obwodu, i nazwij je — np. IN, OUT, VCC.",
  noBoards:
    "Płytka ({{ids}}) nie może być w komponencie: jej program nie ruszy w zamkniętym pudełku. Zostaw ją na schemacie obok.",
  close: "Zamknij",
  cancel: "Anuluj",
  mine: "Moje komponenty",
  remove: "Usuń komponent",
  confirmRemove: "Usunąć komponent „{{name}}” z biblioteki? Schematy, na których już jest, zachowają swoją kopię.",
  button: "Zapisz jako komponent",
};

export const en: typeof pl = {
  title: "Save as a component",
  intro:
    "The drawing's ports are the pins on the outline. Drag a pin to another place or side, and the box's corner to give it more room.",
  name: "Name",
  pins: "Pins",
  sides: { left: "left", right: "right", top: "top", bottom: "bottom" },
  dragHint: "drag the pins and the box's corner",
  keysHint: "Or pick a pin and move it with the arrow keys — to another side too.",
  size: "Size",
  fit: "Fit to the pins",
  preview: "The component: drag its pins around the outline",
  save: "Save the component",
  replaceButton: "Replace the component",
  willReplace: "There is a component of this name — saving replaces it.",
  saving: "Saving…",
  saved:
    "Saved “{{name}}”. It is in the element library (the Elements button on a schematic), under My components — on every schematic, in every note.",
  done: "Done",
  failed: "It could not be saved — please try again.",
  replace: "There is a component “{{name}}” already. Replace it with this one?",
  noPorts:
    "This drawing has no ports. Put a Port element (element library → Connections) wherever the component connects to the rest of a circuit, and name it — e.g. IN, OUT, VCC.",
  noBoards:
    "A board ({{ids}}) cannot be inside a component: its program would not run in a closed box. Keep it on the schematic beside it.",
  close: "Close",
  cancel: "Cancel",
  mine: "My components",
  remove: "Delete the component",
  confirmRemove: "Delete the component “{{name}}” from the library? Schematics it is on keep their copy.",
  button: "Save as a component",
};
