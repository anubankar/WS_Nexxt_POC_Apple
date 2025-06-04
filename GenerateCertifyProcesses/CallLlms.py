import openai

def CallforLLm(systemprompt, usrprompt, model:str):
    response = openai.chat.completions.create(
            model=model,
            temperature=0.0,
            messages=[ {"role": "system", "content": systemprompt},
                        {"role": "user", "content": usrprompt}
                    ]        
        )

        # Extract JSON output from OpenAI response
    json_output = response.choices[0].message.content
    print(json_output)
    json_output = json_output.replace("```json", "").replace("```", "").strip()
    return json_output