# Interfaccia sistema GLS

L'obiettivo di questo progetto è quello di caricare sul sistema GLS le spedizioni presenti in dei file che vengono mensilmente prodotti da un cliente.

Nel file sono presenti indirizzi toponomastici, compilati manualmente, che devono essere validati e normalizzati mediante il metodo già implmentato nell'app che si trova in questa codebase.

Quello che vogliamo ora è una app più complessa e completa che permetta di caricare un file tra quelli analizzati in questo progetto.

Se nel nome del file excel c'è la parola "OLD" per ogni riga vanno aggiunti due campi: il numero di colli, da valorizzare fisso a 1, e il peso da valorizzare fisso a 3.

Se nel nome file c'è la parola "NEW" per ogni riga vanno aggiunti gli stessi due campi descritti sopra ma n. colli valorizzato a 2 e il peso fisso a 3 (come sopra).

I dati di ciascuna riga vanno caricati tramite api nel sistema GLS.

Deve essere creato un campo note concatenando il numero progressivo riportato a colonna 1 con il n. di telefono (cellulare o fisso a seconda di quello valorizzato) e se presente il campo indicazioni