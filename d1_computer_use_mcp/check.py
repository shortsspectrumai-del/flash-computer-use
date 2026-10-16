"""Read-only provider diagnostic with optional synthetic image inference."""
import argparse
import asyncio
import json
from PIL import Image, ImageDraw
from .d1_engine import D1Engine


async def check(inference):
    engine = D1Engine()
    try:
        result = {'provider':engine.settings.provider,'model':engine.settings.model,'endpoint':engine.settings.base_url}
        if engine.settings.provider == 'ollama':
            result.update(await engine.check_ollama())
        if inference:
            image = Image.new('RGB',(384,256),'white')
            ImageDraw.Draw(image).rectangle((80,40,300,210),fill='red')
            result['synthetic_image_test'] = await engine.evaluate(image, {
                'red': {'type':'noul','instructions':'Is there a large red rectangle on a white background?'},
                'color': {'type':'choice','instructions':'What color is the large rectangle?', 'criteria':{'red':'Red','blue':'Blue','green':'Green'}},
                'redness': {'type':'score','instructions':'How much red is present?', 'criteria':['None','Some','A large red rectangle']},
            })
        print(json.dumps(result,indent=2))
    finally:
        await engine.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inference',action='store_true')
    args = parser.parse_args()
    asyncio.run(check(args.inference))


if __name__=='__main__':
    main()
