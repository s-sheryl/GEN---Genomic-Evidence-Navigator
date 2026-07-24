import requests





def get_clinvar_data(gene, variant):


    try:


        search_url = (

            "https://eutils.ncbi.nlm.nih.gov/"
            "entrez/eutils/esearch.fcgi"

        )



        params = {


            "db":
            "clinvar",


            "term":
            f"{gene}[Gene] AND {variant}[Variant Name]",


            "retmode":
            "json"

        }



        response = requests.get(

            search_url,

            params=params,

            timeout=15

        )



        data = response.json()



        ids = data["esearchresult"]["idlist"]





        if not ids:


            return {

                "status":
                "No ClinVar record found"

            }





        clinvar_id = ids[0]







        summary_url = (

            "https://eutils.ncbi.nlm.nih.gov/"
            "entrez/eutils/esummary.fcgi"

        )




        summary = requests.get(

            summary_url,

            params={

                "db":
                "clinvar",

                "id":
                clinvar_id,

                "retmode":
                "json"

            },

            timeout=15

        ).json()





        record = summary["result"][clinvar_id]





        classification = record.get(

            "germline_classification",

            {}

        )





        conditions=[]




        for item in classification.get(

            "trait_set",

            []

        ):


            name=item.get(

                "trait_name"

            )


            if name:

                conditions.append(
                    name
                )








        return {


            "status":

            "ClinVar record found",



            "clinvar_id":

            clinvar_id,



            "clinical_significance":

            classification.get(

                "description",

                "Not available"

            ),



            "review_status":

            classification.get(

                "review_status",

                "Not available"

            ),



            "conditions":

            conditions


        }






    except Exception as error:


        return {


            "status":

            "ClinVar connection error",


            "error":

            str(error)

        }