from django.contrib import admin
from .models import LigneProd, Produit, ObjectifHebdo, Realisation, MouvementTempsReel, EtatLigne

# Register your models here.


admin.site.register(LigneProd)
admin.site.register(Produit)
admin.site.register(ObjectifHebdo)
admin.site.register(Realisation)
admin.site.register(MouvementTempsReel)
admin.site.register(EtatLigne)